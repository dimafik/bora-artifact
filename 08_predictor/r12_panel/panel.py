"""E-B + E-C: train eight detector families on the same data, then attack all of
them white-box with the same strength.

WHY THE PUBLISHED ATTACK WAS TOO WEAK.  mm_adaptive.py initialises the search at
    ar1(max(rho_min, 0.85))
so even when it asks for rho_min = 0 it starts at autocorrelation 0.85 and never
leaves that basin -- the realised autocorrelation at rho_min = 0 was 0.73.  The
constraint is inactive there, so nothing pushes the optimiser out and nothing
pulls it back.  It reported worst-case AUC 0.733; a search that actually reaches
low autocorrelation reports 0.120.  tramer2020adaptive, which the paper cites for
its methodology, is about exactly this failure mode.

So this harness follows the adaptive-evaluation protocol properly: several
initialisations (white noise and AR(1) at three levels), several learning rates,
several seeds, and the WORST result over all of them is what gets reported.

Non-differentiable models (random forest, k-NN) are attacked by transfer from the
logistic surrogate, and that is stated rather than hidden.
"""
import sys, json, time
import numpy as np
import torch
import torch.nn as nn

sys.path.insert(0, ".")
sys.path.insert(0, "..")
sys.path.insert(0, "../predictor")
import gen
from model import ScorePredictor, CONFIG

K, MEAN, STD = gen.K, gen.MEAN, gen.STD
N_ATK = 200                      # per class, matching r11_pgd_strong
RHOS = [0.0, 0.3, 0.6, 0.8]
LRS = [0.1, 0.3, 1.0]
SEEDS = [0, 1, 2]
STEPS = 300
INITS = ["white", "ar0.3", "ar0.6", "ar0.9"]

if "--smoke" in sys.argv:                 # end-to-end check before the long run
    N_ATK, RHOS, LRS, SEEDS, STEPS = 50, [0.0, 0.8], [0.3], [0], 20
    INITS = ["white", "ar0.9"]


# ---------------------------------------------------------------- differentiable
def summarise_torch(X):
    """40 summary stats, differentiable.  Mirrors gen.summarise."""
    out = []
    for c in range(X.shape[2]):
        ch = X[:, :, c]
        m = ch.mean(1)
        s = ch.std(1) + 1e-9
        z = (ch - m[:, None]) / s[:, None]
        ac = (z[:, :-1] * z[:, 1:]).mean(1)
        out += [m, s, ch.min(1).values, ch.max(1).values, ac]
    return torch.stack(out, dim=1)


def autocorr1(r):
    z = (r - r.mean(1, keepdim=True)) / (r.std(1, keepdim=True) + 1e-9)
    return (z[:, :-1] * z[:, 1:]).mean(1)


# ---------------------------------------------------------------- model wrappers
class Torchable:
    """Anything whose anomaly score is a differentiable function of raw RTT."""
    def __init__(self, name, params, fn):
        self.name, self.params, self.fn = name, params, fn
        self.differentiable = True

    def score_raw(self, r):                      # r: (B,K) tensor -> (B,)
        return self.fn(gen.window_torch(r))

    def score_np(self, raw):
        with torch.no_grad():
            return self.score_raw(torch.tensor(raw)).numpy()


class Sklearnish:
    def __init__(self, name, params, clf, surrogate):
        self.name, self.params, self.clf = name, params, clf
        self.surrogate = surrogate
        self.differentiable = False

    def score_np(self, raw):
        X = gen.window_torch(torch.tensor(raw)).detach()
        return self.clf.predict_proba(gen.summarise(X))[:, 1]


def build_models(Xtr, ytr, retrained_path):
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.neighbors import KNeighborsClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline

    Str = gen.summarise(Xtr); ynp = ytr.numpy()
    models = []

    # 1. zero-parameter statistic.  Sign fixed on the training split.
    sgn = 1.0 if gen.auc(ynp, Xtr.numpy()[:, :, 6].std(1)) >= 0.5 else -1.0
    models.append(Torchable("std(dRTT) statistic", 0,
                            lambda X, s=sgn: s * X[:, :, 6].std(1)))

    # 2. logistic on 40 summary stats
    lr = make_pipeline(StandardScaler(), LogisticRegression(max_iter=5000)).fit(Str, ynp)
    sc, lg = lr.named_steps["standardscaler"], lr.named_steps["logisticregression"]
    W = torch.tensor(lg.coef_[0] / sc.scale_, dtype=torch.float32)
    B = torch.tensor(float(lg.intercept_[0] - (lg.coef_[0] * sc.mean_ / sc.scale_).sum()))
    models.append(Torchable("logistic / 40 summary stats", int(W.numel()) + 1,
                            lambda X, W=W, B=B: summarise_torch(X) @ W + B))
    logistic_surrogate = models[-1]

    # 3-5. torch nets trained on the flattened window.
    # Per-channel standardisation is applied inside the scoring function, so it is
    # part of the model and the white-box attacker differentiates through it too.
    # Without it these nets sit at chance: the raw channels span Tc = 100 down to
    # cc in [0,1], and reporting a crippled baseline would make the comparison
    # meaningless in our own favour.
    CH_M = Xtr.mean(dim=(0, 1))
    CH_S = Xtr.std(dim=(0, 1)) + 1e-6

    def norm(X):
        return (X - CH_M) / CH_S

    def train_net(net, name, epochs=40):
        opt = torch.optim.Adam(net.parameters(), lr=1e-3)
        bce = nn.BCEWithLogitsLoss()
        for _ in range(epochs):
            perm = torch.randperm(len(Xtr))
            for i in range(0, len(Xtr), 128):
                idx = perm[i:i + 128]
                opt.zero_grad()
                bce(net(norm(Xtr[idx])).squeeze(1), ytr[idx]).backward()
                opt.step()
        net.eval()
        return Torchable(name, sum(p.numel() for p in net.parameters()),
                         lambda X, n=net: n(norm(X)).squeeze(1))

    class MLP(nn.Module):
        def __init__(s):
            super().__init__()
            s.f = nn.Sequential(nn.Flatten(), nn.Linear(K * 8, 64), nn.ReLU(),
                                nn.Linear(64, 32), nn.ReLU(), nn.Linear(32, 1))
        def forward(s, X): return s.f(X)

    class CNN(nn.Module):
        def __init__(s):
            super().__init__()
            s.c = nn.Sequential(nn.Conv1d(8, 16, 5, padding=2), nn.ReLU(),
                                nn.Conv1d(16, 16, 5, padding=2), nn.ReLU(),
                                nn.AdaptiveAvgPool1d(1), nn.Flatten(), nn.Linear(16, 1))
        def forward(s, X): return s.c(X.transpose(1, 2))

    class GRU(nn.Module):
        def __init__(s):
            super().__init__()
            s.g = nn.GRU(8, 24, batch_first=True)
            s.o = nn.Linear(24, 1)
        def forward(s, X): return s.o(s.g(X)[0][:, -1])

    models.append(train_net(MLP(), "MLP 64-32 / raw window"))
    models.append(train_net(CNN(), "1D-CNN"))
    models.append(train_net(GRU(), "GRU"))

    # 6. the deployed Transformer, retrained
    tf = ScorePredictor(CONFIG)
    tf.load_state_dict(torch.load(retrained_path, map_location="cpu"))
    tf.eval()
    models.append(Torchable("Transformer (ours, retrained)",
                            sum(p.numel() for p in tf.parameters()),
                            lambda X, n=tf: n(X)["anomaly"].squeeze(1)))

    # 7-8. non-differentiable, attacked by transfer
    rf = RandomForestClassifier(n_estimators=200, random_state=0).fit(Str, ynp)
    models.append(Sklearnish("random forest / summary stats",
                             sum(t.tree_.node_count for t in rf.estimators_),
                             rf, logistic_surrogate))
    kn = KNeighborsClassifier(15).fit(Str, ynp)
    models.append(Sklearnish("k-NN (k=15) / summary stats", len(Str), kn, logistic_surrogate))
    return models


# ---------------------------------------------------------------- the attack
def init_raw(kind, n, rng):
    if kind == "white":
        return np.stack([gen._white(rng) for _ in range(n)]).astype(np.float32)
    rho = float(kind[2:])
    return np.stack([gen._ar1(rng, rho) for _ in range(n)]).astype(np.float32)


def pgd(target, rho_min, lr, seed, init, steps=STEPS,
        lam_m=2.0, lam_s=2.0, lam_a=4.0):
    rng = np.random.default_rng(seed)
    r = torch.tensor(init_raw(init, N_ATK, rng), dtype=torch.float32, requires_grad=True)
    opt = torch.optim.Adam([r], lr=lr)
    for _ in range(steps):
        opt.zero_grad()
        a = target.score_raw(r)
        loss = (a.mean()
                + lam_m * (r.mean(1) - MEAN).pow(2).mean()
                + lam_s * (r.std(1) - STD).pow(2).mean()
                + lam_a * torch.relu(rho_min - autocorr1(r)).pow(2).mean())
        loss.backward()
        opt.step()
        with torch.no_grad():
            r.clamp_(0.5, 60)
    rr = r.detach()
    return (rr.numpy(),
            float(autocorr1(rr).mean()),
            float(rr.mean()), float(rr.std(1).mean()))


def main():
    t0 = time.time()
    Xtr, ytr, _ = gen.make(500 if "--smoke" in sys.argv else 10000, seed=101)
    Xte, yte, _ = gen.make(200 if "--smoke" in sys.argv else 2000, seed=303)
    models = build_models(Xtr, ytr, "best_mm_r12.pt")
    print("models built (%.0fs)" % (time.time() - t0), flush=True)

    rng = np.random.default_rng(999)
    healthy = np.stack([gen._white(rng) for _ in range(N_ATK)]).astype(np.float32)

    rows = []
    for m in models:
        te = time.time()
        na = gen.auc(yte.numpy(), m.score_np(Xte.numpy()[:, :, 2]))
        h = m.score_np(healthy)
        sweep = {}
        atk = m if m.differentiable else m.surrogate
        for rho in RHOS:
            worst, detail = 1.1, None
            for lr in LRS:
                for seed in SEEDS:
                    for init in INITS:
                        raw, ac, mu, sd = pgd(atk, rho, lr, seed, init)
                        a = gen.auc(np.r_[np.zeros(N_ATK), np.ones(N_ATK)],
                                    np.r_[h, m.score_np(raw)])
                        if a < worst:
                            worst, detail = a, dict(lr=lr, seed=seed, init=init,
                                                    autocorr=round(ac, 3),
                                                    mean=round(mu, 2), std=round(sd, 2))
            sweep["rho_%.1f" % rho] = dict(auc=round(worst, 4), **detail)
            print("  %-32s rho=%.1f  worst AUC=%.4f  (init=%s, realised ac=%.2f)"
                  % (m.name, rho, worst, detail["init"], detail["autocorr"]), flush=True)
        rows.append(dict(name=m.name, params=m.params, differentiable=m.differentiable,
                         non_adaptive=round(na, 4),
                         worst_case=round(min(v["auc"] for v in sweep.values()), 4),
                         sweep=sweep, minutes=round((time.time() - te) / 60, 1)))
        json.dump(rows, open("panel_smoke.json" if "--smoke" in sys.argv else "panel_results.json", "w"), indent=1)
    print("done in %.0f min" % ((time.time() - t0) / 60), flush=True)


if __name__ == "__main__":
    main()
