"""Models for H1/H2/H3. One shared per-node encoder; only the cross-node
operator differs, and every operator is applied BEFORE temporal pooling (r2b
showed that mixing after pooling cannot work). Hand-built feature groups sit
beside them, one group per attack family."""
import numpy as np
import torch
import torch.nn as nn

D = 16


def auc(y, s):
    y = np.asarray(y); s = np.asarray(s)
    o = np.argsort(s)
    r = np.empty(len(s)); r[o] = np.arange(1, len(s) + 1)
    # average ranks for ties
    _, inv, cnt = np.unique(s, return_inverse=True, return_counts=True)
    if (cnt > 1).any():
        sums = np.zeros(len(cnt)); np.add.at(sums, inv, r)
        r = (sums / cnt)[inv]
    np_, nn_ = (y == 1).sum(), (y == 0).sum()
    return (r[y == 1].sum() - np_ * (np_ + 1) / 2) / (np_ * nn_)


# ------------------------------------------------------------------ hand bank
def _corr(X):                      # (B,N,K) -> (B,N,N)
    z = (X - X.mean(2, keepdims=True)) / (X.std(2, keepdims=True) + 1e-9)
    return np.einsum("bik,bjk->bij", z, z) / X.shape[2]


def _pairs(C):
    iu = np.triu_indices(C.shape[1], 1)
    return C[:, iu[0], iu[1]]


def g1(X):                          # pairwise-correlation summary (F1)
    pc = _pairs(_corr(X))
    return np.c_[pc.mean(1), pc.std(1), pc.min(1), pc.max(1),
                 np.sort(pc, 1)[:, :3], np.sort(pc, 1)[:, -3:]]


def g2(X):                          # correlation with the leave-one-out mean (F2)
    B, N, _ = X.shape
    z = (X - X.mean(2, keepdims=True)) / (X.std(2, keepdims=True) + 1e-9)
    tot = z.sum(1, keepdims=True)
    loo = (tot - z) / (N - 1)
    lz = (loo - loo.mean(2, keepdims=True)) / (loo.std(2, keepdims=True) + 1e-9)
    c = (z * lz).mean(2)
    return np.c_[c.min(1), c.mean(1), c.std(1), c.max(1) - c.min(1)]


def g3(X, lags=range(1, 9)):        # lagged cross-correlation gain (F3)
    B, N, K = X.shape
    z = (X - X.mean(2, keepdims=True)) / (X.std(2, keepdims=True) + 1e-9)
    base = _pairs(np.einsum("bik,bjk->bij", z, z) / K)
    best = base.copy()
    for L in lags:
        a, b = z[:, :, L:], z[:, :, :K - L]
        c1 = _pairs(np.einsum("bik,bjk->bij", a, b) / (K - L))
        c2 = _pairs(np.einsum("bik,bjk->bij", b, a) / (K - L))
        best = np.maximum(best, np.maximum(c1, c2))
    gain = best - base
    return np.c_[gain.max(1), gain.mean(1), gain.std(1), base.min(1)]


def g4(X):                          # coupling to PC1, and its spread (F4_partial)
    B, N, K = X.shape
    out = np.empty((B, 4))
    for b in range(B):
        M = X[b] - X[b].mean(1, keepdims=True)
        u, s, vt = np.linalg.svd(M, full_matrices=False)
        fit1 = np.outer(u[:, 0] * s[0], vt[0])
        res = M - fit1
        load = np.abs(u[:, 0])                       # each node's coupling to PC1
        v = res.var(1) / (M.var(1) + 1e-9)           # unexplained share per node
        out[b] = [load.min() / (load.max() + 1e-9), load.std() / (load.mean() + 1e-9),
                  v.max(), v.max() - v.min()]
    return out


def g5(X, seg=10):                  # segment-wise minimum pairwise correlation (F5)
    B, N, K = X.shape
    mins, means = [], []
    for st in range(0, K - seg + 1, seg):
        pc = _pairs(_corr(X[:, :, st:st + seg]))
        mins.append(pc.min(1)); means.append(pc.mean(1))
    mins = np.stack(mins, 1); means = np.stack(means, 1)
    return np.c_[mins.min(1), mins.std(1), means.min(1), means.max(1) - means.min(1)]


GROUPS = {"F1_level": g1, "F2_decorr": g2, "F3_lag": g3, "F4_partial": g4, "F5_burst": g5}


def hand_features(X, groups):
    return np.concatenate([GROUPS[g](X) for g in groups], 1)


# ---------------------------------------------------------------- neural nets
class Net(nn.Module):
    def __init__(s, rel):
        super().__init__()
        s.rel = rel
        s.enc = nn.Sequential(nn.Conv1d(1, D, 5, padding=2), nn.ReLU(),
                              nn.Conv1d(D, D, 5, padding=2), nn.ReLU())
        if rel == "per-node":
            dim = D
        elif rel == "deepsets":
            dim = 3 * D
        elif rel == "relation":
            s.g = nn.Sequential(nn.Linear(2 * D, D), nn.ReLU(), nn.Linear(D, D), nn.ReLU())
            dim = D
        elif rel == "gru-nodes":
            s.gru = nn.GRU(D, D, batch_first=True)
            dim = D
        elif rel == "attention":
            s.att = nn.MultiheadAttention(D, 4, batch_first=True)
            dim = D
        else:
            raise ValueError(rel)
        s.head = nn.Sequential(nn.Linear(2 * dim, 32), nn.ReLU(), nn.Linear(32, 1))

    def forward(s, x):                       # x: (B,N,K)
        B, N, K = x.shape
        h = s.enc(x.reshape(B * N, 1, K)).reshape(B, N, D, K)
        t = h.permute(0, 3, 1, 2).reshape(B * K, N, D)      # (B*K, N, D)
        if s.rel == "per-node":
            m = t                                            # keep the node axis
        elif s.rel == "deepsets":
            m = torch.cat([t.mean(1), t.std(1), t.max(1).values], -1)
        elif s.rel == "relation":
            i, j = torch.triu_indices(N, N, 1)
            m = s.g(torch.cat([t[:, i], t[:, j]], -1)).mean(1)
        elif s.rel == "gru-nodes":
            m = s.gru(t)[0][:, -1]
        elif s.rel == "attention":
            m = s.att(t, t, t, need_weights=False)[0].mean(1)
        if s.rel == "per-node":
            # a per-node scorer, as deployed: score each node on its own series and
            # take the strongest. No statistic is shared between nodes.
            m = m.reshape(B, K, N, -1).permute(0, 2, 1, 3)    # (B,N,K,D)
            z = s.head(torch.cat([m.mean(2), m.max(2).values], -1)).squeeze(-1)
            return z.max(1).values
        m = m.reshape(B, K, -1)
        return s.head(torch.cat([m.mean(1), m.max(1).values], -1)).squeeze(-1)


def fit(net, Xtr, ytr, Xva, yva, lr, epochs=15, patience=3, bs=32):
    opt = torch.optim.Adam(net.parameters(), lr=lr)
    lossf = nn.BCEWithLogitsLoss()
    best, bad, state = -1, 0, None
    for ep in range(epochs):
        net.train()
        perm = torch.randperm(len(Xtr))
        for k in range(0, len(Xtr), bs):
            idx = perm[k:k + bs]
            opt.zero_grad()
            loss = lossf(net(Xtr[idx]), ytr[idx])
            loss.backward(); opt.step()
        a = auc(yva.numpy(), scores(net, Xva))
        if a > best + 1e-4:
            best, bad = a, 0
            state = {k: v.detach().clone() for k, v in net.state_dict().items()}
        else:
            bad += 1
            if bad >= patience:
                break
    net.load_state_dict(state)
    net.eval()
    return net, best


def scores(net, X, bs=64):
    net.eval()
    out = []
    with torch.no_grad():
        for k in range(0, len(X), bs):
            out.append(net(X[k:k + bs]).numpy())
    return np.concatenate(out)
