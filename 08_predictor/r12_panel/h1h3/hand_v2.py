"""The hand-built baseline, given the same effort as the networks.

Feature blocks, each written for a signal an engineer would look for:

  base    pairwise correlation summaries, leave-one-out agreement, level and
          spread deviations, residual after the first principal component
  lagpair pair x lag cross-correlation grid, summarised (max gain, dispersion)
  timing  each node's deviation TIME (argmax of its smoothed deviation from the
          cluster median), then the regularity of those times: successive gaps,
          their spread, and how linear the ordering is -- the T1 signal, written
          out by hand
  group   best-matching peer correlation, the mean correlation to the k nearest
          peers, and the deviation from that group's mean -- the T2 signal

Classifiers: logistic regression, random forest, gradient boosting. The search
budget is the same twelve configurations the networks get.
"""
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

LAGS = (1, 2, 3, 4, 6, 8)


def _z(X):
    return (X - X.mean(2, keepdims=True)) / (X.std(2, keepdims=True) + 1e-9)


def f_base(X):
    B, N, K = X.shape
    z = _z(X)
    C = np.einsum("bik,bjk->bij", z, z) / K
    iu = np.triu_indices(N, 1)
    pc = C[:, iu[0], iu[1]]
    loo = (z.sum(1, keepdims=True) - z) / (N - 1)
    lz = _z(loo)
    c_loo = (z * lz).mean(2)
    lvl, sd = X.mean(2), X.std(2)
    res = []
    for b in range(B):
        M = X[b] - X[b].mean(1, keepdims=True)
        u, s, vt = np.linalg.svd(M, full_matrices=False)
        r = M - np.outer(u[:, 0] * s[0], vt[0])
        res.append((r.var(1) / (M.var(1) + 1e-9)))
    res = np.stack(res)
    return np.c_[pc.mean(1), pc.std(1), pc.min(1), pc.max(1), np.sort(pc, 1)[:, :3],
                 c_loo.min(1), c_loo.mean(1), c_loo.std(1),
                 (lvl.max(1) - lvl.mean(1)) / (lvl.std(1) + 1e-9),
                 (sd.max(1) - sd.mean(1)) / (sd.std(1) + 1e-9),
                 res.max(1), res.max(1) - res.min(1)]


def f_lagpair(X):
    B, N, K = X.shape
    z = _z(X)
    iu = np.triu_indices(N, 1)
    base = (np.einsum("bik,bjk->bij", z, z) / K)[:, iu[0], iu[1]]
    best = base.copy(); bestlag = np.zeros_like(base)
    for L in LAGS:
        a, b_ = z[:, :, L:], z[:, :, :K - L]
        c1 = (np.einsum("bik,bjk->bij", a, b_) / (K - L))[:, iu[0], iu[1]]
        c2 = (np.einsum("bik,bjk->bij", b_, a) / (K - L))[:, iu[0], iu[1]]
        c = np.maximum(c1, c2)
        bestlag = np.where(c > best, L, bestlag)
        best = np.maximum(best, c)
    gain = best - base
    return np.c_[gain.max(1), gain.mean(1), gain.std(1), bestlag.std(1),
                 bestlag.mean(1), (gain > 0.2).mean(1)]


def f_timing(X, width=12):
    """Deviation time per node, then how regular the order of those times is."""
    B, N, K = X.shape
    med = np.median(X, 1, keepdims=True)
    dev = X - med
    ker = np.ones(width) / width
    sm = np.stack([[np.convolve(dev[b, i], ker, "same") for i in range(N)] for b in range(B)])
    peak = sm.max(2)
    tpk = sm.argmax(2).astype(float)
    out = np.empty((B, 6))
    for b in range(B):
        k = min(4, N)
        idx = np.argsort(-peak[b])[:k]
        t = np.sort(tpk[b, idx])
        gaps = np.diff(t)
        out[b] = [gaps.mean() if len(gaps) else 0, gaps.std() if len(gaps) else 0,
                  (gaps.std() / (gaps.mean() + 1e-9)) if len(gaps) else 0,
                  t.max() - t.min(), peak[b, idx].mean(), peak[b].std()]
    return out


def f_group(X, k=2):
    B, N, K = X.shape
    z = _z(X)
    C = np.einsum("bik,bjk->bij", z, z) / K
    np.fill_diagonal(C[0], 0) if False else None
    eye = np.eye(N, dtype=bool)
    Cm = np.where(eye[None], -np.inf, C)
    best = Cm.max(2)                                    # best-matching peer
    topk = np.sort(Cm, 2)[:, :, -k:].mean(2)            # the k nearest peers
    return np.c_[best.min(1), best.mean(1), best.std(1),
                 topk.min(1), topk.mean(1), topk.std(1), (best < 0.3).sum(1)]


BLOCKS = {"base": f_base, "lagpair": f_lagpair, "timing": f_timing, "group": f_group}
SETS = [["base"], ["base", "lagpair"], ["base", "timing", "group"],
        ["base", "lagpair", "timing", "group"]]
CLFS = ["logistic", "rf", "gb"]


def features(X, blocks):
    return np.concatenate([BLOCKS[b](X) for b in blocks], 1)


def make_clf(name, rng):
    if name == "logistic":
        return make_pipeline(StandardScaler(),
                             LogisticRegression(max_iter=5000, C=float(10 ** rng.uniform(-2, 1))))
    if name == "rf":
        return RandomForestClassifier(n_estimators=400, min_samples_leaf=int(rng.integers(1, 6)),
                                      random_state=0, n_jobs=-1)
    return HistGradientBoostingClassifier(max_depth=int(rng.integers(3, 8)),
                                          learning_rate=float(10 ** rng.uniform(-1.5, -0.7)),
                                          max_iter=400, random_state=0)


def score(m, F):
    return m.predict_proba(F)[:, 1] if hasattr(m, "predict_proba") else m.decision_function(F)
