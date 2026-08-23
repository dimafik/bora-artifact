"""R1-1 on the paper's OWN moment-matched benchmark.

An earlier attempt scored lightweight baselines against `best.pt` on rescaled
deployment traces. That was the wrong experiment: rescaling real windows destroys
their temporal structure, so it is a different attack, and `best.pt` is not the
detector the paper reports moment-matched numbers for. `mm_adaptive.py` is, and
its benchmark is synthetic and self-contained:

    healthy  r ~ iid N(8, 3)                       lag-1 autocorrelation ~ 0
    attack   r ~ AR(1) rho=0.9, same marginals     lag-1 autocorrelation ~ 0.9

so the ONLY thing separating the two classes is temporal dependence. Mean and
variance are matched by construction. That is Proposition 8 made concrete: a
detector reading the first two moments is looking at a channel with no signal in
it. The 8-channel window is built from r analytically (`window_t`), and the
reported detector is `best_mm.pt` at AUC 0.923.

This script reuses the SAME generators and the SAME window construction, so every
row of the table is scored on identical data.

Baselines, in increasing order of what they can represent:
    logistic / window means           linear in the first moment -- the Prop-8 case
    logistic / summary stats          + std, min, max, slope
    gradient boosting / summary       nonlinear, still order-blind
    MLP 64-32 / flattened window      nonlinear and order-aware, no attention
    logistic / lag-1 autocorrelation  one hand-crafted feature aimed at this attack

The last one is not a fair architectural rival -- it is a probe. It measures how
much of this benchmark is carried by a single statistic, which is exactly what a
reviewer asking "does this need a Transformer?" deserves to be told.

    python r11_mm_baselines.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
OUT = HERE / "r11_mm_baselines.json"

K = 60                      # CONFIG.window_len
ALPHA = 0.8                 # EWMA smoothing, as in mm_adaptive.window_t
MEAN, STD = 8.0, 3.0        # matched marginals


def ar1(rng, rho, n):
    """AR(1) with stationary marginal N(MEAN, STD): the attack."""
    x = np.empty((n, K), dtype=np.float64)
    x[:, 0] = rng.normal(MEAN, STD, n)
    e = rng.normal(0, STD * np.sqrt(1 - rho ** 2), (n, K))
    for t in range(1, K):
        x[:, t] = MEAN + rho * (x[:, t - 1] - MEAN) + e[:, t]
    return np.clip(x, 0.5, 60)


def white(rng, n):
    """iid N(MEAN, STD): healthy. Same marginals as the attack, no memory."""
    return np.clip(rng.normal(MEAN, STD, (n, K)), 0.5, 60)


def windows(r):
    """The 8 channels mm_adaptive.window_t builds, vectorised over the batch.
    Six of them are constant by construction (delays sit far below the 100 ms
    commit threshold, so cc is always 1); only r and its EWMA carry anything."""
    n = len(r)
    cc = np.ones((n, K))
    CC = np.convolve(np.ones(K), np.ones(20) / 20, mode="same")[None, :].repeat(n, 0)
    dCC = np.diff(CC, axis=1, prepend=CC[:, :1])
    Tc = np.full((n, K), 100.0)
    dz = np.zeros((n, K))
    RTT = np.empty_like(r)
    RTT[:, 0] = r[:, 0]
    for t in range(1, K):
        RTT[:, t] = ALPHA * RTT[:, t - 1] + (1 - ALPHA) * r[:, t]
    dRTT = np.concatenate([np.zeros((n, 1)), np.diff(RTT, axis=1)], axis=1)
    return np.stack([cc, CC, r, RTT, Tc, dCC, dRTT, dz], axis=2).astype(np.float32)


def make(rng, n_each, rho=0.9):
    x = np.concatenate([windows(white(rng, n_each)), windows(ar1(rng, rho, n_each))])
    y = np.concatenate([np.zeros(n_each, int), np.ones(n_each, int)])
    return x, y


def summarise(x):
    n, L, C = x.shape
    tc = np.arange(L, dtype=np.float32) - (L - 1) / 2.0
    denom = (tc * tc).sum()
    return np.concatenate([x.mean(1), x.std(1), x.min(1), x.max(1),
                           (x * tc[None, :, None]).sum(1) / denom], axis=1)


def lag1(x):
    """Lag-1 autocorrelation per channel: the statistic the attack is defined by."""
    xc = x - x.mean(1, keepdims=True)
    num = (xc[:, :-1, :] * xc[:, 1:, :]).sum(1)
    den = (xc ** 2).sum(1) + 1e-8
    return num / den


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
    tr_x, tr_y = make(np.random.default_rng(0), 2000)
    te_x, te_y = make(np.random.default_rng(12345), 2000)
    print("train %s, test %s, positives %.0f%% / %.0f%%"
          % (tr_x.shape, te_x.shape, 100 * tr_y.mean(), 100 * te_y.mean()))
    print("sanity  healthy mean/std %.2f/%.2f   attack mean/std %.2f/%.2f"
          % (te_x[te_y == 0, :, 2].mean(), te_x[te_y == 0, :, 2].std(),
             te_x[te_y == 1, :, 2].mean(), te_x[te_y == 1, :, 2].std()))

    from sklearn.linear_model import LogisticRegression
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.neural_network import MLPClassifier
    from sklearn.preprocessing import StandardScaler

    rows = []

    def evaluate(name, make_clf, featfn, note=""):
        sc = StandardScaler().fit(featfn(tr_x))
        clf = make_clf()
        clf.fit(sc.transform(featfn(tr_x)), tr_y)
        a = auc(te_y, clf.predict_proba(sc.transform(featfn(te_x)))[:, 1])
        coefs = getattr(clf, "coefs_", None)
        size = sum(c.size for c in coefs) if coefs else None
        print("  %-36s AUC %.3f%s%s" % (name, a,
              "   (%d params)" % size if size else "", note))
        rows.append(dict(name=name, auc=round(a, 4), params=size))
        return a

    print("\n=== lightweight baselines, moment-matched attack ===")
    evaluate("logistic / window means (linear)", lambda: LogisticRegression(max_iter=2000),
             lambda x: x.mean(1))
    evaluate("logistic / summary stats (linear)", lambda: LogisticRegression(max_iter=2000),
             summarise)
    evaluate("gradient boosting / summary stats",
             lambda: HistGradientBoostingClassifier(max_iter=200), summarise)
    evaluate("MLP 64-32 / flattened window",
             lambda: MLPClassifier(hidden_layer_sizes=(64, 32), max_iter=400,
                                   random_state=0),
             lambda x: x.reshape(len(x), -1))
    evaluate("logistic / lag-1 autocorrelation", lambda: LogisticRegression(max_iter=2000),
             lag1, note="   <- hand-crafted for this attack")

    try:
        import torch
        sys.path.insert(0, str(HERE / "predictor"))
        from model import ScorePredictor, CONFIG          # noqa: E402
        net = ScorePredictor(CONFIG)
        sd = torch.load(HERE / "best_mm.pt", map_location="cpu")
        net.load_state_dict(sd.get("model_state_dict", sd) if isinstance(sd, dict)
                            and "model_state_dict" in sd else sd)
        net.eval()
        outs = []
        with torch.no_grad():
            for k in range(0, len(te_x), 256):
                outs.append(net(torch.from_numpy(te_x[k:k + 256]))["anomaly"]
                            .squeeze(-1).numpy())
        a = auc(te_y, np.concatenate(outs))
        npar = sum(p.numel() for p in net.parameters())
        print("\n=== reference detector (best_mm.pt) ===")
        print("  %-36s AUC %.3f   (%d params)" % ("Multi-Head Transformer", a, npar))
        print("  paper reports 0.923 on N=200 per class")
        rows.append(dict(name="Multi-Head Transformer (best_mm.pt)",
                         auc=round(a, 4), params=npar))
    except Exception as exc:                              # noqa: BLE001
        print("\n  reference NOT evaluated: %s: %s" % (type(exc).__name__, exc))

    OUT.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print("\nwrote", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
