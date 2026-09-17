"""Relational task generators for H1/H2/H3 (pre-registered 2026-09-16).

Every task is the same question: is ONE node unlike the others (positive), or is
the whole cluster doing the same thing (negative)?  Each node's window is
normalised on its own, so a single node's series carries no class information and
only the relation between nodes does.
"""
import numpy as np

K = 60
FAMILIES = ["F1_level", "F2_decorr", "F3_lag", "F4_partial", "F5_burst"]


def ar1(rng, k=K, rho=0.8, burn=64):
    """AR(1) with the transient discarded, so every window of it has the same
    marginal and spectrum wherever it starts."""
    e = rng.normal(0, 1, k + burn)
    x = np.empty(k + burn)
    a = rng.normal(0, 1 / np.sqrt(1 - rho * rho))
    for t in range(k + burn):
        a = rho * a + e[t]
        x[t] = a
    return x[burn:]


def _norm(x):
    return (x - x.mean()) / (x.std() + 1e-9)


def scenario(rng, fam, single, n=5, common=None):
    """One window: (n, K) after per-node normalisation.

    Every family is built so that a node's OWN normalised series has the same
    distribution whether it is the odd one or not: the class lives in the
    relation between nodes, never in one node's marginals or spectrum. The
    per-node control measures whether that held (pre-registered: <= 0.55).
    """
    long = ar1(rng, K + 12) if common is None else common
    c = long[12:]   # healthy window; F3's odd node takes an earlier window
    gain = rng.uniform(0.85, 1.15, n)
    sig = 0.3
    hot = int(rng.integers(n)) if single else -1
    lift = rng.uniform(0.8, 1.6)
    lag = int(rng.integers(3, 9))
    burst_start = int(rng.integers(0, K - 12))
    out = []
    for i in range(n):
        odd = (i == hot) if single else True          # who deviates
        if fam == "F1_level":
            x = gain[i] * c + rng.normal(0, sig, K)
            if odd:
                x = x + lift * np.abs(rng.normal(1, 0.2, K))
        elif fam == "F2_decorr":
            x = (ar1(rng) if odd else gain[i] * c) + rng.normal(0, sig, K)
        elif fam == "F3_lag":
            off = 12 - lag if odd else 12          # a window of the same process,
            src = long[off:off + K]                # shifted in phase, never wrapped
            x = gain[i] * src + rng.normal(0, sig, K)
        elif fam == "F4_partial":
            # partial decoupling: the odd node keeps the same spectrum (a mixture
            # of two AR(1)s of equal variance) but tracks the cluster only weakly
            w = 0.45 if odd else 1.0
            own = ar1(rng)
            x = gain[i] * (w * c + np.sqrt(max(1 - w * w, 0.0)) * own) + rng.normal(0, sig, K)
        elif fam == "F5_burst":
            x = gain[i] * c + rng.normal(0, sig, K)
            if odd:
                b = np.zeros(K)
                b[burst_start:burst_start + 12] = 2.0 * lift * np.abs(rng.normal(1, 0.2, 12))
                x = x + b
        else:
            raise ValueError(fam)
        out.append(_norm(x))
    return np.stack(out)


def build(n_pairs, seed, fams=FAMILIES, n=5, shuffle_nodes=False):
    """n_pairs windows of each class, families cycled."""
    rng = np.random.default_rng(seed)
    X, y = [], []
    for j in range(n_pairs):
        fam = fams[j % len(fams)]
        for single in (False, True):
            w = scenario(rng, fam, single, n)
            if shuffle_nodes:
                w = w[rng.permutation(n)]
            X.append(w)
            y.append(1 if single else 0)
    return np.stack(X).astype(np.float32), np.array(y, dtype=np.float32)


def build_regions(n_pairs, seed, sizes=(3, 2), shuffle_nodes=False):
    """H2: the common mode is shared inside a region only.

    negative = a whole region deviates (regional congestion)
    positive = one node deviates
    The leave-one-out mean over ALL nodes is the wrong reference here.
    """
    rng = np.random.default_rng(seed)
    n = sum(sizes)
    X, y = [], []
    for _ in range(n_pairs):
        for single in (False, True):
            commons = [ar1(rng) for _ in sizes]
            hot_region = int(rng.integers(len(sizes)))
            idx, out = 0, []
            hot_node = int(rng.integers(sizes[hot_region]))
            lift = rng.uniform(0.8, 1.6)
            for r, size in enumerate(sizes):
                for i in range(size):
                    odd = (r == hot_region) and (single is False or i == hot_node)
                    x = rng.uniform(0.85, 1.15) * commons[r] + rng.normal(0, 0.3, K)
                    if odd:
                        x = x + lift * np.abs(rng.normal(1, 0.2, K))
                    out.append(_norm(x))
                    idx += 1
            w = np.stack(out)
            if shuffle_nodes:
                w = w[rng.permutation(n)]
            X.append(w)
            y.append(1 if single else 0)
    return np.stack(X).astype(np.float32), np.array(y, dtype=np.float32)
