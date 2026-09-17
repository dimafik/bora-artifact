"""T1/T2: two tasks where attention has a structural reason to win.

Both are motivated by the deployment, not by the architecture:

T1 coordinated timing. An adversary that delays several orderers does not delay
   them at the same instant; it walks through them. The class is whether the
   deviations across nodes follow one ordered cascade (attack) or fire
   independently (congestion). Deciding it means aligning node i's deviation with
   node j's at an unknown lag -- a pairwise, content-dependent alignment. A
   symmetric average cannot do it and a fixed feature bank needs a pair x lag
   grid that grows as N^2 x L.

T2 sparse reference group at large N. In a wide cluster only a few orderers share
   a fault domain with the target; the rest are irrelevant. The class is whether
   the target deviates from ITS OWN reference group. Averaging over all N nodes
   dilutes the comparison as N grows; selecting the right few is what attention
   is for.

Every node's window is normalised on its own, as everywhere else in this study.
"""
import numpy as np

K = 60


def ar1(rng, k=K, rho=0.8, burn=64):
    e = rng.normal(0, 1, k + burn)
    x = np.empty(k + burn)
    a = rng.normal(0, 1 / np.sqrt(1 - rho * rho))
    for t in range(k + burn):
        a = rho * a + e[t]
        x[t] = a
    return x[burn:]


def _norm(x):
    return (x - x.mean()) / (x.std() + 1e-9)


def t1_window(rng, attack, n=7, m=4, sig=0.3):
    """m of n nodes deviate. attack: one ordered cascade with a fixed step lag.
    control: the same m deviations, independent times, same marginals."""
    c = ar1(rng)
    who = rng.choice(n, m, replace=False)
    amp = rng.uniform(0.9, 1.4)
    width = 12
    if attack:
        step = int(rng.integers(3, 7))
        t0 = int(rng.integers(0, K - width - step * (m - 1)))
        times = [t0 + step * i for i in range(m)]
    else:
        times = list(rng.integers(0, K - width, m))
    out = []
    for i in range(n):
        x = rng.uniform(0.85, 1.15) * c + rng.normal(0, sig, K)
        if i in who:
            t = times[list(who).index(i)]
            bump = np.zeros(K)
            bump[t:t + width] = amp * np.abs(rng.normal(1, 0.15, width))
            x = x + bump
        out.append(_norm(x))
    return np.stack(out)


def t2_window(rng, attack, n=21, group=3, sig=0.3):
    """Every node belongs to a small fault domain with its own common mode; only
    the target's own domain is the right reference. attack: the target deviates
    from its domain. control: its whole domain deviates together."""
    ngroups = n // group
    commons = [ar1(rng) for _ in range(ngroups)]
    lift = rng.uniform(0.9, 1.5)
    hot_group = int(rng.integers(ngroups))
    hot_node = int(rng.integers(group))
    out = []
    for g in range(ngroups):
        for i in range(group):
            odd = (g == hot_group) and (attack is False or i == hot_node)
            x = rng.uniform(0.85, 1.15) * commons[g] + rng.normal(0, sig, K)
            if odd:
                x = x + lift * np.abs(rng.normal(1, 0.2, K))
            out.append(_norm(x))
    extra = n - ngroups * group
    for _ in range(extra):
        out.append(_norm(rng.uniform(0.85, 1.15) * commons[0] + rng.normal(0, sig, K)))
    return np.stack(out)


def build(task, n_pairs, seed, n=None, shuffle_nodes=True):
    rng = np.random.default_rng(seed)
    X, y = [], []
    for _ in range(n_pairs):
        for attack in (False, True):
            if task == "T1":
                w = t1_window(rng, attack, n or 7)
            elif task == "T2":
                w = t2_window(rng, attack, n or 21)
            else:
                raise ValueError(task)
            if shuffle_nodes:
                w = w[rng.permutation(len(w))]
            X.append(w)
            y.append(1 if attack else 0)
    return np.stack(X).astype(np.float32), np.array(y, dtype=np.float32)
