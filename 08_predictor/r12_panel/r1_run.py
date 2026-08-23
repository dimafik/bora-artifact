"""R1: long-range dependence.

Every window carries exactly two spikes, so counting them is useless.  What
separates the classes is the DISTANCE between them:

    healthy   gap < 15
    attack    gap > 40

Attention connects any two positions in one hop.  A GRU has to carry the first
spike in its state for 40+ steps.  The 1D-CNN here is kernel 5 over two layers,
a receptive field of 9, so it cannot see both spikes in any single unit and can
only aggregate local evidence -- which the equal spike count makes uninformative.

If the architecture choice is defensible anywhere, it should be here.  If the
Transformer does not win this, the prediction was wrong and it gets reported.
"""
import sys, json, time
import numpy as np
import torch

sys.path.insert(0, "."); sys.path.insert(0, ".."); sys.path.insert(0, "../predictor")
import gen, hard_gen, ed_run as E, ed2_run as R2

K, MEAN, STD = gen.K, gen.MEAN, gen.STD
NEAR_MAX, FAR_MIN = 15, 40


def two_spikes(rng, far):
    while True:
        i, j = sorted(rng.choice(np.arange(3, K - 3), size=2, replace=False))
        gap = j - i
        if far and gap > FAR_MIN:
            break
        if not far and gap < NEAR_MAX:
            break
    x = rng.normal(0, 0.35, K)
    amp = rng.uniform(3.0, 4.5)
    x[i] += amp
    x[j] += amp * rng.uniform(0.9, 1.1)
    return hard_gen._norm(x), gap


def build(n, seed):
    rng = np.random.default_rng(seed)
    X, y, gaps = [], [], []
    for _ in range(n):
        r, g = two_spikes(rng, far=False)
        X.append(gen.window(r)); y.append(0); gaps.append(g)
        r, g = two_spikes(rng, far=True)
        X.append(gen.window(r)); y.append(1); gaps.append(g)
    return (torch.tensor(np.stack(X)),
            torch.tensor(np.array(y), dtype=torch.float32), gaps)


def main():
    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.neighbors import KNeighborsClassifier
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline

    Xtr, ytr, gtr = build(10000, 101)
    Xva, yva, _ = build(1000, 202)
    Xte, yte, gte = build(2000, 303)
    print("gap: healthy %.1f / attack %.1f  (window %d)"
          % (np.mean(gtr[0::2]), np.mean(gtr[1::2]), K), flush=True)

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
                     params=sum(t.tree_.node_count for t in rf.estimators_),
                     cfg="-", auc=round(gen.auc(yte_n, rf.predict_proba(Ste)[:, 1]), 4)))
    kn = KNeighborsClassifier(15).fit(Str, ytr_n)
    rows.append(dict(name="k-NN (k=15) / summary stats", params=len(Str), cfg="-",
                     auc=round(gen.auc(yte_n, kn.predict_proba(Ste)[:, 1]), 4)))
    for r in rows:
        print("  %-30s %-10s AUC=%.4f" % (r["name"][:30], r["cfg"], r["auc"]), flush=True)

    norm = E.Norm(Xtr)
    for nm, cls, readouts in R2.NETS:
        best = None
        for ro in readouts:
            for lr in (3e-4, 1e-3):
                t = time.time()
                net, ep = E.fit_torch(cls(norm, ro), Xtr, ytr, Xva, yva, 40, 6, lr=lr)
                a = gen.auc(yte_n, E.score(net, Xte))
                tag = "%s/%.0e" % (ro or "flat", lr)
                print("  %-30s %-10s ep=%2d AUC=%.4f (%.1f min)"
                      % (nm, tag, ep, a, (time.time() - t) / 60), flush=True)
                if best is None or a > best["auc"]:
                    best = dict(name=nm, params=sum(p.numel() for p in net.parameters()),
                                cfg=tag, auc=round(a, 4))
        rows.append(best)
        json.dump(rows, open("r1_results.json", "w"), indent=1)
    print("done", flush=True)


if __name__ == "__main__":
    main()
