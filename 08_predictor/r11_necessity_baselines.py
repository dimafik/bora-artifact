"""R1-1: extend the paper's own necessity table with lightweight discriminators.

Reviewer 1 asks whether an attention model is required, or whether a standard
lightweight discriminator would do. Table II already answers half of it: on the
sophisticated (moment-matched + AR(1)) adversary the S-Raft score threshold sits
at 0.50, the best of the per-channel mean/std statistics reaches 0.74, and the
Transformer reaches 0.93. What it does not report is the middle of the ladder --
a nonlinear model on those same statistics, and an order-aware model without
attention. Those are what "a standard lightweight discriminator" means, and they
are the rows the reviewer is really asking about.

This script reuses `necessity_proof.make_matched_dataset` and its train/test
seed offsets (0 / 10_000) unchanged, so every number lands in the same table as
the paper's 0.74 and 0.93. Two earlier attempts are superseded and kept only as
a record:

    lightweight_baselines.py  scored against best.pt on rescaled deployment
                              traces -- rescaling destroys temporal structure,
                              so it was a different attack
    r11_mm_baselines.py       used mm_adaptive.py's generator, which is built
                              for white-box PGD, not for architecture
                              comparison; its derived EWMA channels leak the
                              autocorrelation into a second moment (std of dRTT
                              alone reaches 0.999 there, vs 0.590 here)

    python r11_necessity_baselines.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
OUT = HERE / "r11_necessity_baselines.json"
sys.path.insert(0, str(HERE / "predictor"))

from necessity_proof import make_matched_dataset      # noqa: E402

N_TRACES, N_TICKS = 40, 4000                          # necessity_proof.py defaults


def summarise(x):
    """The statistic vector Table II's 'best single feature' row searches over,
    handed to a model all at once instead of one at a time, plus min/max/slope."""
    n, L, C = x.shape
    tc = np.arange(L, dtype=np.float64) - (L - 1) / 2.0
    denom = (tc * tc).sum()
    return np.concatenate([x.mean(1), x.std(1), x.min(1), x.max(1),
                           (x * tc[None, :, None]).sum(1) / denom], axis=1)


def auc(y, s):
    y = np.asarray(y).astype(int)
    s = np.asarray(s, dtype=float)
    pos, neg = (y == 1).sum(), (y == 0).sum()
    if pos == 0 or neg == 0:
        return float("nan")
    order = np.argsort(s, kind="mergesort")
    ranks = np.empty(len(s), dtype=float)
    ss = s[order]
    i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and ss[j + 1] == ss[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return (ranks[y == 1].sum() - pos * (pos + 1) / 2.0) / (pos * neg)


def main():
    results = {}
    for attacker in ["naive", "moment_matched", "sophisticated"]:
        tr_x, tr_y = make_matched_dataset(N_TRACES, N_TICKS, seed_offset=0,
                                          attacker=attacker)
        te_x, te_y = make_matched_dataset(N_TRACES // 4, N_TICKS, seed_offset=10_000,
                                          attacker=attacker)
        tr_x = tr_x.astype(np.float64)
        te_x = te_x.astype(np.float64)
        print("\n=== %s ===  train %s  test %s  (byz %.0f%%)"
              % (attacker, tr_x.shape, te_x.shape, 100 * te_y.mean()))

        from sklearn.linear_model import LogisticRegression
        from sklearn.ensemble import HistGradientBoostingClassifier
        from sklearn.neural_network import MLPClassifier
        from sklearn.preprocessing import StandardScaler

        row = {}

        def evaluate(name, make_clf, featfn):
            Xtr = featfn(tr_x)
            sc = StandardScaler().fit(Xtr)
            clf = make_clf()
            clf.fit(sc.transform(Xtr), tr_y)
            a = auc(te_y, clf.predict_proba(sc.transform(featfn(te_x)))[:, 1])
            coefs = getattr(clf, "coefs_", None)
            size = sum(c.size for c in coefs) if coefs else None
            row[name] = dict(auc=round(a, 4), params=size)
            print("  %-36s AUC %.3f%s" % (name, a,
                  "   (%d params)" % size if size else ""))

        # Best single per-channel mean/std, recomputed here so the paper's 0.74
        # anchor is visible in the same run rather than taken on trust.
        best, bname = 0.0, ""
        for c in range(te_x.shape[2]):
            for stat, fn in (("mean", lambda v: v.mean(1)), ("std", lambda v: v.std(1))):
                s = fn(te_x)[:, c]
                a = max(auc(te_y, s), auc(te_y, -s))
                if a > best:
                    best, bname = a, "ch%d (%s)" % (c, stat)
        row["best single mean/std feature"] = dict(auc=round(best, 4), params=None)
        print("  %-36s AUC %.3f   [%s]" % ("best single mean/std feature", best, bname))

        evaluate("logistic / summary stats (linear)",
                 lambda: LogisticRegression(max_iter=5000), summarise)
        evaluate("gradient boosting / summary stats",
                 lambda: HistGradientBoostingClassifier(max_iter=200), summarise)
        evaluate("MLP 64-32 / flattened window",
                 lambda: MLPClassifier(hidden_layer_sizes=(64, 32), max_iter=400,
                                       random_state=0),
                 lambda x: x.reshape(len(x), -1))
        results[attacker] = row

    OUT.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print("\nwrote", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
