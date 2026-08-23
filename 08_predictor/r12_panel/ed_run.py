"""E-D: do the three hard tasks give a measured reason to deploy the Transformer?

Every model is trained from scratch on the same windows for each task, including
the Transformer, with the same budget and the same early stopping.  The panel
benchmark could not separate architectures because it saturated; these cannot be
solved by window-level location or scale, since every window is renormalised to
mean 8 / std 3 after the attack is written in.

    H1  a short attack segment (5-25 of 60 steps) inside an otherwise healthy
        window -- summary statistics are diluted, locating it is worth more
    H2  four attack families mixed
    H3  leave-one-family-out: train on three families, test on the fourth

Read H1 and H3.  H2 is reported for completeness but the 40 summary statistics
include per-channel min and max, which reach isolated spikes without any notion
of order, so it is the weakest of the three as an architecture test.
"""
import sys, json, time, copy
import numpy as np
import torch
import torch.nn as nn

sys.path.insert(0, "."); sys.path.insert(0, ".."); sys.path.insert(0, "../predictor")
import gen, hard_gen
from model import ScorePredictor, CONFIG

TRAIN_PAIRS, VAL_PAIRS, TEST_PAIRS = 10000, 1000, 2000
SMOKE = "--smoke" in sys.argv
if SMOKE:
    TRAIN_PAIRS, VAL_PAIRS, TEST_PAIRS = 600, 200, 400


def score(model, X, bs=512):
    model.eval()
    out = []
    with torch.no_grad():
        for i in range(0, len(X), bs):
            out.append(model(X[i:i + bs]))
    return torch.cat(out).squeeze(-1).numpy()


def fit_torch(net, Xtr, ytr, Xva, yva, epochs, patience, lr=1e-3, tag=""):
    opt = torch.optim.Adam(net.parameters(), lr=lr)
    bce = nn.BCEWithLogitsLoss()
    best, best_state, bad = -1.0, None, 0
    for ep in range(epochs):
        net.train()
        perm = torch.randperm(len(Xtr))
        for i in range(0, len(Xtr), 128):
            idx = perm[i:i + 128]
            opt.zero_grad()
            bce(net(Xtr[idx]).squeeze(-1), ytr[idx]).backward()
            opt.step()
        a = gen.auc(yva.numpy(), score(net, Xva))
        if a > best + 1e-4:
            best, best_state, bad = a, copy.deepcopy(net.state_dict()), 0
        else:
            bad += 1
            if bad >= patience:
                break
    net.load_state_dict(best_state)
    net.eval()
    return net, ep + 1


class Norm(nn.Module):
    """Per-channel standardisation folded into the model, as in the panel run."""
    def __init__(self, X):
        super().__init__()
        self.register_buffer("m", X.mean(dim=(0, 1)))
        self.register_buffer("s", X.std(dim=(0, 1)) + 1e-6)

    def forward(self, X):
        return (X - self.m) / self.s


def make_nets(Xtr):
    K = gen.K
    n = Norm(Xtr)

    class MLP(nn.Module):
        def __init__(s):
            super().__init__()
            s.n = n
            s.f = nn.Sequential(nn.Flatten(), nn.Linear(K * 8, 64), nn.ReLU(),
                                nn.Linear(64, 32), nn.ReLU(), nn.Linear(32, 1))
        def forward(s, X): return s.f(s.n(X))

    class CNN(nn.Module):
        def __init__(s):
            super().__init__()
            s.n = n
            s.c = nn.Sequential(nn.Conv1d(8, 16, 5, padding=2), nn.ReLU(),
                                nn.Conv1d(16, 16, 5, padding=2), nn.ReLU(),
                                nn.AdaptiveAvgPool1d(1), nn.Flatten(), nn.Linear(16, 1))
        def forward(s, X): return s.c(s.n(X).transpose(1, 2))

    class GRUNet(nn.Module):
        def __init__(s):
            super().__init__()
            s.n = n
            s.g = nn.GRU(8, 24, batch_first=True)
            s.o = nn.Linear(24, 1)
        def forward(s, X): return s.o(s.g(s.n(X))[0][:, -1])

    class TF(nn.Module):
        def __init__(s):
            super().__init__()
            s.m = ScorePredictor(CONFIG)
        def forward(s, X): return s.m(X)["anomaly"]

    return [("MLP 64-32", MLP()), ("1D-CNN", CNN()),
            ("GRU", GRUNet()), ("Transformer (ours)", TF())]


def run_task(name, Xtr, ytr, Xva, yva, Xte, yte):
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.neighbors import KNeighborsClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline

    t0 = time.time()
    Str, Ste = gen.summarise(Xtr), gen.summarise(Xte)
    ytr_n, yte_n = ytr.numpy(), yte.numpy()
    rows = []

    s6 = Xtr.numpy()[:, :, 6].std(1)
    sgn = 1.0 if gen.auc(ytr_n, s6) >= 0.5 else -1.0
    rows.append(("std(dRTT) statistic", 0,
                 gen.auc(yte_n, sgn * Xte.numpy()[:, :, 6].std(1))))

    lg = make_pipeline(StandardScaler(), LogisticRegression(max_iter=5000)).fit(Str, ytr_n)
    rows.append(("logistic / 40 summary stats", 41,
                 gen.auc(yte_n, lg.decision_function(Ste))))

    rf = RandomForestClassifier(n_estimators=200, random_state=0).fit(Str, ytr_n)
    rows.append(("random forest / summary stats",
                 sum(t.tree_.node_count for t in rf.estimators_),
                 gen.auc(yte_n, rf.predict_proba(Ste)[:, 1])))

    kn = KNeighborsClassifier(15).fit(Str, ytr_n)
    rows.append(("k-NN (k=15) / summary stats", len(Str),
                 gen.auc(yte_n, kn.predict_proba(Ste)[:, 1])))

    for nm, net in make_nets(Xtr):
        ep = 8 if SMOKE else (40 if "Transformer" in nm else 60)
        net, used = fit_torch(net, Xtr, ytr, Xva, yva, ep, 3 if SMOKE else 8)
        rows.append((nm, sum(p.numel() for p in net.parameters()),
                     gen.auc(yte_n, score(net, Xte))))
        print("    %-28s epochs=%2d  AUC=%.4f" % (nm, used, rows[-1][2]), flush=True)

    print("  [%s] %.1f min" % (name, (time.time() - t0) / 60), flush=True)
    return [dict(name=n, params=p, auc=round(a, 4)) for n, p, a in rows]


def main():
    out = {}
    for task in ("H1", "H2"):
        print("=== %s" % task, flush=True)
        Xtr, ytr, _ = hard_gen.build(task, TRAIN_PAIRS, seed=101)
        Xva, yva, _ = hard_gen.build(task, VAL_PAIRS, seed=202)
        Xte, yte, _ = hard_gen.build(task, TEST_PAIRS, seed=303)
        out[task] = run_task(task, Xtr, ytr, Xva, yva, Xte, yte)
        json.dump(out, open("ed_smoke.json" if SMOKE else "ed_results.json", "w"), indent=1)

    for held in hard_gen.FAMILIES:
        tr = [f for f in hard_gen.FAMILIES if f != held]
        key = "H3_holdout_%s" % held
        print("=== %s" % key, flush=True)
        Xtr, ytr, _ = hard_gen.build("H2", TRAIN_PAIRS, seed=401, families=tr)
        Xva, yva, _ = hard_gen.build("H2", VAL_PAIRS, seed=402, families=tr)
        Xte, yte, _ = hard_gen.build("H2", TEST_PAIRS, seed=403, families=[held])
        out[key] = run_task(key, Xtr, ytr, Xva, yva, Xte, yte)
        json.dump(out, open("ed_smoke.json" if SMOKE else "ed_results.json", "w"), indent=1)
    print("done", flush=True)


if __name__ == "__main__":
    main()
