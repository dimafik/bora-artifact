"""Second-generation models: every family gets the same modern recipe.

The first study gave each model one shared encoder, a fixed width and a two-point
learning-rate sweep. That is enough to ask "does a relational operator help" and
not enough to ask "which operator is better". Here each family gets:

  * the same stem (a strided temporal convolution),
  * the same depth, width, dropout, augmentation and optimiser schedule,
  * the same random-search budget over the same-sized space,

and only the mixing operator differs:

  per-node    none
  deepsets    symmetric statistics over nodes (mean, std, max)
  relation    a pairwise MLP over node pairs
  gru-nodes   a GRU along the node axis (order-dependent)
  attention   axial self-attention: over time within a node, then over nodes at
              each step, with a learned CLS token for the final pooling
"""
import numpy as np
import torch
import torch.nn as nn


def auc(y, s):
    y = np.asarray(y); s = np.asarray(s)
    order = np.argsort(s)
    r = np.empty(len(s)); r[order] = np.arange(1, len(s) + 1)
    u, inv, cnt = np.unique(s, return_inverse=True, return_counts=True)
    if (cnt > 1).any():
        sums = np.zeros(len(cnt)); np.add.at(sums, inv, r); r = (sums / cnt)[inv]
    p, q = (y == 1).sum(), (y == 0).sum()
    return (r[y == 1].sum() - p * (p + 1) / 2) / (p * q)


class Block(nn.Module):
    def __init__(s, rel, d, heads, drop):
        super().__init__()
        s.rel = rel
        s.n1, s.n2 = nn.LayerNorm(d), nn.LayerNorm(d)
        s.drop = nn.Dropout(drop)
        s.ff = nn.Sequential(nn.Linear(d, 2 * d), nn.GELU(), nn.Dropout(drop), nn.Linear(2 * d, d))
        if rel == "attention":
            s.t_att = nn.MultiheadAttention(d, heads, dropout=drop, batch_first=True)
            s.n_att = nn.MultiheadAttention(d, heads, dropout=drop, batch_first=True)
        elif rel == "deepsets":
            s.mix = nn.Linear(3 * d, d)
        elif rel == "relation":
            s.g = nn.Sequential(nn.Linear(2 * d, d), nn.GELU(), nn.Linear(d, d))
        elif rel == "gru-nodes":
            s.gru = nn.GRU(d, d, batch_first=True, bidirectional=False)
        elif rel == "per-node":
            s.mix = nn.Identity()

    def forward(s, h):                                  # h: (B,N,T,d)
        B, N, T, d = h.shape
        x = s.n1(h)
        if s.rel == "attention":                        # along time, per node
            z = x.reshape(B * N, T, d)
            h = h + s.drop(s.t_att(z, z, z, need_weights=False)[0]).reshape(B, N, T, d)
        x = s.n2(h)
        y = x.permute(0, 2, 1, 3).reshape(B * T, N, d)  # across nodes, per step
        if s.rel == "attention":
            m = s.n_att(y, y, y, need_weights=False)[0]
        elif s.rel == "deepsets":
            ctx = torch.cat([y.mean(1, keepdim=True), y.std(1, keepdim=True),
                             y.max(1, keepdim=True).values], -1).expand(-1, N, -1)
            m = s.mix(ctx)
        elif s.rel == "relation":
            pair = s.g(torch.cat([y.unsqueeze(2).expand(-1, -1, N, -1),
                                  y.unsqueeze(1).expand(-1, N, -1, -1)], -1))
            m = pair.mean(2)
        elif s.rel == "gru-nodes":
            m = s.gru(y)[0]
        else:
            m = torch.zeros_like(y)
        h = h + s.drop(m).reshape(B, T, N, d).permute(0, 2, 1, 3)
        return h + s.drop(s.ff(h))


class Net(nn.Module):
    def __init__(s, rel, d=64, layers=2, heads=4, drop=0.1, stride=2):
        super().__init__()
        s.rel = rel
        s.stem = nn.Sequential(nn.Conv1d(1, d, 5, stride=stride, padding=2), nn.GELU(),
                               nn.Conv1d(d, d, 5, padding=2), nn.GELU())
        s.blocks = nn.ModuleList([Block(rel, d, heads, drop) for _ in range(layers)])
        s.cls = nn.Parameter(torch.randn(1, 1, d) * 0.02)
        s.pool = nn.MultiheadAttention(d, heads, batch_first=True) if rel == "attention" else None
        s.norm = nn.LayerNorm(d)
        s.head = nn.Sequential(nn.Linear(2 * d, d), nn.GELU(), nn.Dropout(drop), nn.Linear(d, 1))

    def forward(s, x):                                  # (B,N,K)
        B, N, K = x.shape
        h = s.stem(x.reshape(B * N, 1, K))
        d, T = h.shape[1], h.shape[2]
        h = h.reshape(B, N, d, T).permute(0, 1, 3, 2)   # (B,N,T,d)
        for blk in s.blocks:
            h = blk(h)
        h = s.norm(h)
        v = h.mean(2)                                   # pool time -> (B,N,d)
        if s.rel == "attention":
            q = s.cls.expand(B, -1, -1)
            g = s.pool(q, v, v, need_weights=False)[0].squeeze(1)
        else:
            g = v.mean(1)
        return s.head(torch.cat([g, v.max(1).values], -1)).squeeze(-1)


def augment(x, rng, permute=True, jitter=0.05, crop=0.0):
    B, N, K = x.shape
    if permute:
        idx = np.argsort(rng.random((B, N)), 1)
        x = torch.stack([x[b, idx[b]] for b in range(B)])
    if jitter:
        x = x * (1 + jitter * torch.randn(B, N, 1))
    if crop:
        w = int(K * (1 - crop))
        st = int(rng.integers(0, K - w + 1))
        x = torch.nn.functional.pad(x[:, :, st:st + w], (0, K - w), mode="replicate")
    return x


def fit(rel, cfg, Xtr, ytr, Xva, yva, seed=0, max_epochs=60, patience=10, verbose=False):
    torch.manual_seed(seed)
    rng = np.random.default_rng(seed)
    net = Net(rel, d=cfg["d"], layers=cfg["layers"], heads=cfg["heads"], drop=cfg["drop"])
    opt = torch.optim.AdamW(net.parameters(), lr=cfg["lr"], weight_decay=cfg["wd"])
    Xtr_t, ytr_t = torch.tensor(Xtr), torch.tensor(ytr)
    Xva_t = torch.tensor(Xva)
    bs = cfg["bs"]
    steps = max(1, len(Xtr_t) // bs) * max_epochs
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=cfg["lr"], total_steps=steps,
                                                pct_start=0.15)
    lossf = nn.BCEWithLogitsLoss()
    best, bad, state, done = -1, 0, None, 0
    for ep in range(max_epochs):
        net.train()
        perm = torch.randperm(len(Xtr_t))
        for k in range(0, len(Xtr_t) - bs + 1, bs):
            i = perm[k:k + bs]
            xb = augment(Xtr_t[i], rng, permute=cfg["aug_perm"], jitter=cfg["aug_jit"])
            yb = ytr_t[i] * (1 - cfg["smooth"]) + 0.5 * cfg["smooth"]
            opt.zero_grad()
            lossf(net(xb), yb).backward()
            nn.utils.clip_grad_norm_(net.parameters(), 1.0)
            opt.step()
            if done < steps - 1:
                sched.step(); done += 1
        a = auc(yva, predict(net, Xva_t))
        if verbose:
            print("    ep%02d val %.4f" % (ep, a), flush=True)
        if a > best + 1e-4:
            best, bad = a, 0
            state = {k: v.detach().clone() for k, v in net.state_dict().items()}
        else:
            bad += 1
            if bad >= patience:
                break
    net.load_state_dict(state); net.eval()
    return net, best


def predict(net, X, bs=64):
    net.eval()
    if not torch.is_tensor(X):
        X = torch.tensor(X)
    out = []
    with torch.no_grad():
        for k in range(0, len(X), bs):
            out.append(net(X[k:k + bs]).numpy())
    return np.concatenate(out)


SPACE = dict(d=[32, 64, 96], layers=[1, 2, 3], heads=[2, 4, 8], drop=[0.0, 0.1, 0.2],
             lr=[3e-4, 1e-3, 3e-3], wd=[0.0, 0.01, 0.05], bs=[32, 64],
             aug_perm=[True, False], aug_jit=[0.0, 0.05], smooth=[0.0, 0.1])


def sample_cfg(rng):
    c = {k: v[int(rng.integers(len(v)))] for k, v in SPACE.items()}
    while c["d"] % c["heads"]:
        c["heads"] = SPACE["heads"][int(rng.integers(len(SPACE["heads"])))]
    return c
