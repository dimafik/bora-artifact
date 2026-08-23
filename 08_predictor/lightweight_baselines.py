"""R1-1: does the detection task actually need a Transformer?

Reviewer 1 asked whether an attention-based model is required, or whether a
standard lightweight discriminator would do. The paper already argues that a
LINEAR functional cannot work (Proposition 8: against a moment-matched adversary
any linear detector sits at chance). That answers "must it be nonlinear?", not
"must it be a Transformer?".

So we train the obvious lightweight alternatives on the same windows, the same
split, and the same labels, and score them on the same two regimes the paper
reports for the reference model:

    non-adaptive attack   -- the easy regime
    moment-matched attack -- mean and variance matched to healthy traffic,
                             the regime that puts linear detectors at 0.50

Baselines, in increasing order of what they can represent:
    logistic regression on window means      (linear, the Prop-8 case)
    logistic regression on richer summaries  (mean/std/min/max/slope per channel)
    gradient boosting on the same summaries  (nonlinear, no temporal order)
    small MLP on the flattened window        (nonlinear, order-aware but no attention)

The interesting comparison is the third and fourth against the reference. If a
GBM on summary statistics matches the Transformer, the architecture claim is
weak and we should say so. If it does not, the gap is the answer to R1-1.

    python lightweight_baselines.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
DATA = HERE / "data_small"
OUT = HERE / "r11_baselines.json"


def load_all():
    """Every window with its frame. Splitting is done afterwards on the frame's
    own `seed` column: parsing the filename concatenates every digit in it
    ("byzantine_seed2000" gives 2000, but a stem with two numbers does not), so
    the column is the only reliable key."""
    xs, dfs = [], []
    for f in sorted(DATA.glob("*.parquet")):
        npy = f.with_suffix(".npy")
        if not npy.exists():
            continue
        xs.append(np.load(npy))
        dfs.append(pd.read_parquet(f))
    if not xs:
        return None, None
    return np.concatenate(xs).astype(np.float32), pd.concat(dfs, ignore_index=True)


def split_by_seed(x, df, frac=0.6):
    """Hold out whole seeds, never windows: windows from one seed share a
    trajectory, so a random window split would leak the test set into training."""
    seeds = np.sort(df["seed"].unique())
    cut = seeds[int(len(seeds) * frac)] if len(seeds) > 1 else seeds[0]
    tr = df["seed"].to_numpy() < cut
    return x[tr], df[tr].reset_index(drop=True), x[~tr], df[~tr].reset_index(drop=True)


def summarise(x):
    """Per-channel summary statistics: what a non-temporal model gets to see."""
    n, L, C = x.shape
    t = np.arange(L, dtype=np.float32)
    tc = t - t.mean()
    denom = (tc * tc).sum()
    feats = [x.mean(1), x.std(1), x.min(1), x.max(1),
             (x * tc[None, :, None]).sum(1) / denom]      # least-squares slope
    return np.concatenate(feats, axis=1)


def auc(y, s):
    """Rank-based AUC; ties get average ranks."""
    y = np.asarray(y).astype(int)
    s = np.asarray(s, dtype=float)
    pos, neg = (y == 1).sum(), (y == 0).sum()
    if pos == 0 or neg == 0:
        return float("nan")
    order = np.argsort(s, kind="mergesort")
    ranks = np.empty(len(s), dtype=float)
    sorted_s = s[order]
    i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and sorted_s[j + 1] == sorted_s[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2.0 + 1.0
        i = j + 1
    return (ranks[y == 1].sum() - pos * (pos + 1) / 2.0) / (pos * neg)


def moment_match(x, y):
    """Rescale each attack window so its per-channel mean and std match the
    healthy windows. This is the adversary of Proposition 8: first two moments
    carry no signal afterwards, so anything linear in them is at chance."""
    x = x.copy()
    healthy = x[y == 0]
    hm, hs = healthy.mean((0, 1)), healthy.std((0, 1)) + 1e-8
    idx = np.where(y == 1)[0]
    am = x[idx].mean(1, keepdims=True)
    asd = x[idx].std(1, keepdims=True) + 1e-8
    x[idx] = (x[idx] - am) / asd * hs[None, None, :] + hm[None, None, :]
    return x


def main():
    all_x, all_df = load_all()
    if all_x is None:
        print("NO_DATA in %s" % DATA)
        return 1
    tr_x, tr_df, te_x, te_df = split_by_seed(all_x, all_df)
    tr_y = tr_df["byzantine"].to_numpy().astype(int)
    te_y = te_df["byzantine"].to_numpy().astype(int)
    print("seeds %d, train %s, test %s, positives %.1f%% / %.1f%%"
          % (all_df["seed"].nunique(), tr_x.shape, te_x.shape,
             100 * tr_y.mean(), 100 * te_y.mean()))

    te_mm = moment_match(te_x, te_y)

    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.neural_network import MLPClassifier
    from sklearn.preprocessing import StandardScaler

    def evaluate(name, make, featfn):
        Xtr = featfn(tr_x)
        sc = StandardScaler().fit(Xtr)
        clf = make()
        clf.fit(sc.transform(Xtr), tr_y)
        a_plain = auc(te_y, clf.predict_proba(sc.transform(featfn(te_x)))[:, 1])
        a_mm = auc(te_y, clf.predict_proba(sc.transform(featfn(te_mm)))[:, 1])
        npar = getattr(clf, "coefs_", None)
        size = sum(c.size for c in npar) if npar else None
        print("  %-34s non-adaptive %.3f   moment-matched %.3f%s"
              % (name, a_plain, a_mm, "   (%d params)" % size if size else ""))
        return dict(name=name, non_adaptive=round(a_plain, 4),
                    moment_matched=round(a_mm, 4), params=size)

    rows = []
    print("\n=== lightweight baselines ===")
    rows.append(evaluate("logistic / window means (linear)",
                         lambda: LogisticRegression(max_iter=2000),
                         lambda x: x.mean(1)))
    rows.append(evaluate("logistic / summary stats (linear)",
                         lambda: LogisticRegression(max_iter=2000), summarise))
    rows.append(evaluate("gradient boosting / summary stats",
                         lambda: HistGradientBoostingClassifier(max_iter=200), summarise))
    rows.append(evaluate("MLP 64-32 / flattened window",
                         lambda: MLPClassifier(hidden_layer_sizes=(64, 32),
                                               max_iter=400, random_state=0),
                         lambda x: x.reshape(len(x), -1)))

    # Reference model on the SAME test windows, so the comparison is like for
    # like. Its anomaly head is the byzantine detector; the score head predicts
    # the S-Raft score and is not what R1-1 is about.
    try:
        import torch
        sys.path.insert(0, str(HERE / "predictor"))
        from model import ScorePredictor, CONFIG           # noqa: E402
        net = ScorePredictor(CONFIG)
        sd = torch.load(HERE / "model_small" / "best.pt", map_location="cpu")
        net.load_state_dict(sd.get("model_state_dict", sd.get("state_dict", sd))
                            if isinstance(sd, dict) else sd)
        net.eval()

        def score(arr):
            outs = []
            with torch.no_grad():
                for k in range(0, len(arr), 256):
                    o = net(torch.from_numpy(arr[k:k + 256]))
                    outs.append(o["anomaly"].squeeze(-1).numpy())
            return np.concatenate(outs)

        a_plain = auc(te_y, score(te_x))
        a_mm = auc(te_y, score(te_mm))
        npar = sum(p.numel() for p in net.parameters())
        print("\n=== reference model ===")
        print("  %-34s non-adaptive %.3f   moment-matched %.3f   (%d params)"
              % ("Multi-Head Transformer", a_plain, a_mm, npar))
        rows.append(dict(name="Multi-Head Transformer (reference)",
                         non_adaptive=round(a_plain, 4),
                         moment_matched=round(a_mm, 4), params=npar))
    except Exception as exc:                                # noqa: BLE001
        print("\n  reference model NOT evaluated: %s: %s" % (type(exc).__name__, exc))

    OUT.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print("\nwrote", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
