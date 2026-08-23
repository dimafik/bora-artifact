"""E-D: benchmarks that summary statistics cannot solve by construction.

The panel benchmark saturated -- a 41-parameter logistic on 40 summary statistics
reached AUC 1.000, so no architecture could show an advantage.  That says the
benchmark cannot separate architectures, not that architecture is irrelevant.

Every window here is renormalised to mean 8 / std 3 AFTER the attack is written
in, so window-level location and scale carry no information at all.  What differs
between healthy and attack is only the temporal SHAPE, and between families only
which shape.  A model that cannot look at order has nothing left to use.

Families (all marginal-matched):
    A  ar1        autocorrelated delay, the family the paper trained on
    B  burst      periodic spikes
    C  varshift   variance changepoint mid-window
    D  heavytail  a few large spikes, quiet otherwise
"""
import numpy as np
import gen

K, MEAN, STD = gen.K, gen.MEAN, gen.STD
FAMILIES = ["ar1", "burst", "varshift", "heavytail"]


def _norm(x):
    """Force window mean/std, so no summary statistic of level or spread helps."""
    x = (x - x.mean()) / (x.std() + 1e-9) * STD + MEAN
    return np.clip(x, 0.5, None)


def healthy(rng):
    return _norm(rng.normal(0, 1, K))


def attack(rng, family):
    if family == "ar1":
        rho = rng.uniform(0.85, 0.95)
        x = np.empty(K); x[0] = rng.normal()
        e = rng.normal(0, np.sqrt(1 - rho ** 2), K)
        for t in range(1, K):
            x[t] = rho * x[t - 1] + e[t]
    elif family == "burst":
        p = rng.integers(5, 16)
        x = rng.normal(0, 0.4, K)
        x[::p] += rng.uniform(2.0, 3.5)
    elif family == "varshift":
        cut = rng.integers(K // 4, 3 * K // 4)
        x = np.concatenate([rng.normal(0, 0.35, cut),
                            rng.normal(0, 1.6, K - cut)])
    elif family == "heavytail":
        x = rng.normal(0, 0.35, K)
        for i in rng.choice(K, size=rng.integers(2, 5), replace=False):
            x[i] += rng.uniform(3.0, 5.0) * rng.choice([-1, 1])
    else:
        raise ValueError(family)
    return _norm(x)


def partial(rng, family, lo=5, hi=25):
    """H1: the attack occupies only the last L steps; the rest is healthy.

    A statistic taken over the whole window is diluted by L/K, so locating the
    segment is worth more than summarising it."""
    L = int(rng.integers(lo, hi + 1))
    a = attack(rng, family)
    h = rng.normal(0, 1, K)
    x = h.copy()
    x[K - L:] = (a[K - L:] - MEAN) / STD          # splice, then renormalise whole
    return _norm(x), L


def build(task, n, seed, families=None, lo=10):
    """Returns (X, y, meta).  X is the 8-channel window the daemon builds."""
    rng = np.random.default_rng(seed)
    fam = families or FAMILIES
    X, y, meta = [], [], []
    for _ in range(n):
        X.append(gen.window(healthy(rng))); y.append(0); meta.append("healthy")
        f = fam[rng.integers(len(fam))]
        if task == "H1":
            r, L = partial(rng, f)
            meta.append("%s/L=%d" % (f, L))
        else:
            r = attack(rng, f)
            meta.append(f)
        X.append(gen.window(r)); y.append(1)
    import torch
    return (torch.tensor(np.stack(X)),
            torch.tensor(np.array(y), dtype=torch.float32), meta)


def partial_anywhere(rng, family, lo=5, hi=25):
    """H1b: the attack segment is placed ANYWHERE in the window.

    The first version put it at the end, which happens to coincide with a GRU's
    last-hidden-state readout -- a benchmark bias in one architecture's favour.
    Randomising the position removes it."""
    L = int(rng.integers(lo, hi + 1))
    s = int(rng.integers(0, K - L + 1))
    a = attack(rng, family)
    x = rng.normal(0, 1, K)
    x[s:s + L] = (a[s:s + L] - MEAN) / STD
    return _norm(x), L, s
