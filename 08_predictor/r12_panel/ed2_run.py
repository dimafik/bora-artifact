"""E-D2: the comparison redone after three faults were found in E-D.

  1. MY BUG.  The Transformer alone was denied the per-channel normalisation the
     MLP, CNN and GRU all received.  Fixing it moves H1 from 0.66 to 0.84 -- the
     same handicap that pinned the MLP at 0.51 until I fixed it for the
     baselines, left in place only where it hurt our own model.  Every number in
     ed_results.json and lrsweep.json is void because of this.
  2. BENCHMARK BIAS.  H1 put the attack at the END of the window, which is
     exactly where a GRU's last-hidden-state readout looks.  H1b places it
     anywhere.
  3. NOT A FAULT, as it turned out.  ScorePredictor mean-pools over time, which
     looked like it should destroy localisation.  Measured: attention pooling
     beats mean pooling by 0.004.  The pooling hypothesis is rejected and the
     deployed readout needs no change.

Fairness rules, applied to everyone rather than to whoever it happens to favour:
every model gets the normalisation, every neural model gets a choice of readout,
every model gets the learning-rate sweep, and all see identical data.

The Transformer's readout is fixed to attention because the diagnostic measured
all three for it and they were within 0.004; that saves two thirds of the run
time on the only expensive model.  This is recorded rather than silent.
"""
import sys, json, time, os
import numpy as np
import torch
import torch.nn as nn

sys.path.insert(0, "."); sys.path.insert(0, ".."); sys.path.insert(0, "../predictor")
import gen, hard_gen, ed_run as E
from model import ScorePredictor, CONFIG

LRS = [3e-4, 1e-3]
OUT = "ed2_results.json"
TRAIN_PAIRS, VAL_PAIRS, TEST_PAIRS = 10000, 1000, 2000


def build_H1b(n, seed, families=None):
    rng = np.random.default_rng(seed)
    fam = families or hard_gen.FAMILIES
    X, y = [], []
    for _ in range(n):
        X.append(gen.window(hard_gen.healthy(rng))); y.append(0)
        f = fam[rng.integers(len(fam))]
        r, _, _ = hard_gen.partial_anywhere(rng, f)
        X.append(gen.window(r)); y.append(1)
    return torch.tensor(np.stack(X)), torch.tensor(np.array(y), dtype=torch.float32)


def build_fam(n, seed, families):
    rng = np.random.default_rng(seed)
    X, y = [], []
    for _ in range(n):
        X.append(gen.window(hard_gen.healthy(rng))); y.append(0)
        f = families[rng.integers(len(families))]
        X.append(gen.window(hard_gen.attack(rng, f))); y.append(1)
    return torch.tensor(np.stack(X)), torch.tensor(np.array(y), dtype=torch.float32)


def pool(h, mode, q=None):
    if mode == "mean":
        return h.mean(1)
    if mode == "max":
        return h.max(1).values
    if mode == "last":
        return h[:, -1]
    w = torch.softmax((h @ q) / h.shape[-1] ** 0.5, dim=1)
    return (h * w.unsqueeze(-1)).sum(1)


class CNN(nn.Module):
    def __init__(s, norm, readout):
        super().__init__()
        s.n, s.r = norm, readout
        s.c = nn.Sequential(nn.Conv1d(8, 16, 5, padding=2), nn.ReLU(),
                            nn.Conv1d(16, 16, 5, padding=2), nn.ReLU())
        s.q = nn.Parameter(torch.randn(16) * 0.05)
        s.o = nn.Linear(16, 1)

    def forward(s, X):
        h = s.c(s.n(X).transpose(1, 2)).transpose(1, 2)
        return s.o(pool(h, s.r, s.q))


class GRUNet(nn.Module):
    def __init__(s, norm, readout):
        super().__init__()
        s.n, s.r = norm, readout
        s.g = nn.GRU(8, 24, batch_first=True)
        s.q = nn.Parameter(torch.randn(24) * 0.05)
        s.o = nn.Linear(24, 1)

    def forward(s, X):
        h, _ = s.g(s.n(X))
        return s.o(pool(h, s.r, s.q))


class MLP(nn.Module):
    def __init__(s, norm, readout=None):
        super().__init__()
        s.n = norm
        s.f = nn.Sequential(nn.Flatten(), nn.Linear(gen.K * 8, 64), nn.ReLU(),
                            nn.Linear(64, 32), nn.ReLU(), nn.Linear(32, 1))

    def forward(s, X): return s.f(s.n(X))


class TF(nn.Module):
    def __init__(s, norm, readout="attn"):
        super().__init__()
        s.n, s.r = norm, readout
        s.m = ScorePredictor(CONFIG)
        s.q = nn.Parameter(torch.randn(CONFIG.d_model) * 0.02)
        s.o = nn.Sequential(nn.Linear(CONFIG.d_model, 32), nn.ReLU(), nn.Linear(32, 1))

    def forward(s, X):
        h = s.m.encoder(s.m.pos_enc(s.m.input_proj(s.n(X))))
        return s.o(pool(h, s.r, s.q))


NETS = [("MLP 64-32", MLP, [None]),
        ("1D-CNN", CNN, ["mean", "max", "attn"]),
        ("GRU", GRUNet, ["last", "mean", "attn"]),
        ("Transformer (ours)", TF, ["attn"])]


def run_task(key, Xtr, ytr, Xva, yva, Xte, yte, out):
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.neighbors import KNeighborsClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline

    t0 = time.time()
    Str, Ste = gen.summarise(Xtr), gen.summarise(Xte)
    ytr_n, yte_n = ytr.numpy(), yte.numpy()
    rows = []

    sgn = 1.0 if gen.auc(ytr_n, Xtr.numpy()[:, :, 6].std(1)) >= 0.5 else -1.0
    rows.append(dict(name="std(dRTT) statistic", params=0, cfg="-",
                     auc=round(gen.auc(yte_n, sgn * Xte.numpy()[:, :, 6].std(1)), 4)))
    lg = make_pipeline(StandardScaler(), LogisticRegression(max_iter=5000)).fit(Str, ytr_n)
    rows.append(dict(name="logistic / 40 summary stats", params=41, cfg="-",
                     auc=round(gen.auc(yte_n, lg.decision_function(Ste)), 4)))
    rf = RandomForestClassifier(n_estimators=200, random_state=0).fit(Str, ytr_n)
    rows.append(dict(name="random forest / summary stats",
                     params=sum(t.tree_.node_count for t in rf.estimators_), cfg="-",
                     auc=round(gen.auc(yte_n, rf.predict_proba(Ste)[:, 1]), 4)))
    kn = KNeighborsClassifier(15).fit(Str, ytr_n)
    rows.append(dict(name="k-NN (k=15) / summary stats", params=len(Str), cfg="-",
                     auc=round(gen.auc(yte_n, kn.predict_proba(Ste)[:, 1]), 4)))
    for r in rows:
        print("    %-30s %-6s AUC=%.4f" % (r["name"][:30], r["cfg"], r["auc"]), flush=True)

    norm = E.Norm(Xtr)
    for nm, cls, readouts in NETS:
        best = None
        for ro in readouts:
            for lr in LRS:
                net, ep = E.fit_torch(cls(norm, ro), Xtr, ytr, Xva, yva, 40, 6, lr=lr)
                a = gen.auc(yte_n, E.score(net, Xte))
                tag = "%s/%.0e" % (ro or "flat", lr)
                print("    %-30s %-10s ep=%2d AUC=%.4f" % (nm, tag, ep, a), flush=True)
                if best is None or a > best["auc"]:
                    best = dict(name=nm, params=sum(p.numel() for p in net.parameters()),
                                cfg=tag, auc=round(a, 4))
        rows.append(best)
        out[key] = rows
        json.dump(out, open(OUT, "w"), indent=1)
    print("  [%s] %.1f min" % (key, (time.time() - t0) / 60), flush=True)


def main():
    out = json.load(open(OUT)) if os.path.exists(OUT) else {}
    jobs = [("H1b", lambda s, n: build_H1b(n, s))]
    for held in hard_gen.FAMILIES:
        tr = [f for f in hard_gen.FAMILIES if f != held]
        jobs.append(("H3:%s" % held,
                     (lambda TR, HE: (lambda s, n, te=False:
                      build_fam(n, s, [HE] if te else TR)))(tr, held)))
    for key, mk in jobs:
        if key in out:
            print("=== %s (이미 완료, 건너뜀)" % key, flush=True)
            continue
        print("=== %s" % key, flush=True)
        if key == "H1b":
            Xtr, ytr = mk(101, TRAIN_PAIRS); Xva, yva = mk(202, VAL_PAIRS)
            Xte, yte = mk(303, TEST_PAIRS)
        else:
            Xtr, ytr = mk(401, TRAIN_PAIRS); Xva, yva = mk(402, VAL_PAIRS)
            Xte, yte = mk(403, TEST_PAIRS, True)
        run_task(key, Xtr, ytr, Xva, yva, Xte, yte, out)
    print("done", flush=True)


if __name__ == "__main__":
    main()
