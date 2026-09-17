"""E-A: attribution on REAL telemetry, split by segment.

The deployed daemon does not answer "is something wrong"; it answers "which
orderer goes in B_t". The daemon log carries 18 independent N=7 segments in which
exactly one orderer was delayed, so that question can be asked of real data with a
group split: a whole segment is train, val or test, and no window crosses.

Two regimes, and the pair is the point:
  RAW  : the delayed node's RTT really is higher, so a per-node scorer should work
  NORM : each node's window standardised, which deletes exactly the cue a
         moment-matched adversary deletes, leaving only the relation between nodes

usage: python run_real.py [--quick]
"""
import os, sys, json, time
import numpy as np
import torch
import torch.nn as nn

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
import real_seg
import rel_models as M

WIN, STRIDE, NN = 60, 20, 7
SEEDS = [0, 1, 2]
RES = "results_real.json"


def windows_of(arr, stride=STRIDE):
    return [arr[i:i + WIN] for i in range(0, arr.shape[0] - WIN + 1, stride)]


def segment_data(seg, mode, cap=None, rng=None):
    ids, hot, arr = seg
    tgt = ids.index(next(iter(hot)))
    ws = windows_of(arr)
    if cap and len(ws) > cap:
        idx = rng.choice(len(ws), cap, replace=False)
        ws = [ws[i] for i in idx]
    X = []
    for w in ws:
        r = w.T.astype(np.float64)                        # (N, WIN)
        if mode == "norm":
            r = (r - r.mean(1, keepdims=True)) / (r.std(1, keepdims=True) + 1e-6)
        else:
            r = np.log1p(np.clip(r, 0, None))             # raw keeps the level
        X.append(r)
    y = np.full(len(X), tgt)
    return np.asarray(X, dtype=np.float32), y


def split_segments(segs, seed):
    rng = np.random.default_rng(seed)
    idx = rng.permutation(len(segs))
    n_te = max(3, len(segs) // 5)
    return ([segs[i] for i in idx[2 * n_te:]],
            [segs[i] for i in idx[n_te:2 * n_te]],
            [segs[i] for i in idx[:n_te]])


def make(segs, mode, cap, seed):
    rng = np.random.default_rng(seed)
    Xs, ys = [], []
    for s in segs:
        X, y = segment_data(s, mode, cap, rng)
        if len(X):
            Xs.append(X); ys.append(y)
    return np.concatenate(Xs), np.concatenate(ys)


# ----------------------------------------------------------- attribution models
class AttrNet(nn.Module):
    """Same encoder as the synthetic study; the head scores every node."""
    def __init__(s, rel, d=32):
        super().__init__()
        s.rel, s.d = rel, d
        s.enc = nn.Sequential(nn.Conv1d(1, d, 5, padding=2), nn.ReLU(),
                              nn.Conv1d(d, d, 5, padding=2), nn.ReLU())
        if rel == "per-node":
            dim = d
        elif rel == "deepsets":
            dim = 3 * d
        elif rel == "relation":
            s.g = nn.Sequential(nn.Linear(2 * d, d), nn.ReLU(), nn.Linear(d, d), nn.ReLU())
            dim = 2 * d
        elif rel == "attention":
            s.att = nn.MultiheadAttention(d, 4, batch_first=True)
            dim = 2 * d
        else:
            raise ValueError(rel)
        s.head = nn.Sequential(nn.Linear(2 * dim, 32), nn.ReLU(), nn.Linear(32, 1))

    def forward(s, x):                                   # (B,N,K) -> (B,N)
        B, N, K = x.shape
        h = s.enc(x.reshape(B * N, 1, K)).reshape(B, N, s.d, K)
        t = h.permute(0, 3, 1, 2).reshape(B * K, N, s.d)  # (B*K,N,d)
        if s.rel == "per-node":
            u = t
        elif s.rel == "deepsets":
            ctx = torch.cat([t.mean(1, keepdim=True), t.std(1, keepdim=True),
                             t.max(1, keepdim=True).values], -1).expand(-1, N, -1)
            u = torch.cat([t, ctx[..., s.d:]], -1)
        elif s.rel == "relation":
            pair = s.g(torch.cat([t.unsqueeze(2).expand(-1, -1, N, -1),
                                  t.unsqueeze(1).expand(-1, N, -1, -1)], -1))
            u = torch.cat([t, pair.mean(2)], -1)
        elif s.rel == "attention":
            u = torch.cat([t, s.att(t, t, t, need_weights=False)[0]], -1)
        u = u.reshape(B, K, N, -1).permute(0, 2, 1, 3)    # (B,N,K,dim)
        return s.head(torch.cat([u.mean(2), u.max(2).values], -1)).squeeze(-1)


def top1(logits, y):
    return float((logits.argmax(1) == y).mean())


def fit_net(rel, Xtr, ytr, Xva, yva, lr, epochs, patience, bs=32):
    torch.manual_seed(0)
    net = AttrNet(rel)
    opt = torch.optim.Adam(net.parameters(), lr=lr)
    lossf = nn.CrossEntropyLoss()
    Xtr_t, ytr_t = torch.tensor(Xtr), torch.tensor(ytr, dtype=torch.long)
    best, bad, state = -1, 0, None
    for ep in range(epochs):
        net.train()
        perm = torch.randperm(len(Xtr_t))
        for k in range(0, len(Xtr_t), bs):
            i = perm[k:k + bs]
            opt.zero_grad()
            lossf(net(Xtr_t[i]), ytr_t[i]).backward()
            opt.step()
        a = top1(predict(net, Xva), yva)
        if a > best + 1e-4:
            best, bad = a, 0
            state = {k: v.detach().clone() for k, v in net.state_dict().items()}
        else:
            bad += 1
            if bad >= patience:
                break
    net.load_state_dict(state); net.eval()
    return net


def predict(net, X, bs=64):
    net.eval()
    out = []
    with torch.no_grad():
        for k in range(0, len(X), bs):
            out.append(net(torch.tensor(X[k:k + bs])).numpy())
    return np.concatenate(out)


# --------------------------------------------------------------- hand baseline
def node_features(X):
    """Per-node features, the ones an engineer would write: level, spread,
    agreement with the other nodes, lagged agreement, residual after PC1."""
    B, N, K = X.shape
    z = (X - X.mean(2, keepdims=True)) / (X.std(2, keepdims=True) + 1e-9)
    tot = z.sum(1, keepdims=True)
    loo = (tot - z) / (N - 1)
    lz = (loo - loo.mean(2, keepdims=True)) / (loo.std(2, keepdims=True) + 1e-9)
    c_loo = (z * lz).mean(2)                                    # agreement
    lagged = np.stack([(z[:, :, L:] * lz[:, :, :K - L]).mean(2) for L in (1, 2, 4, 8)], -1).max(-1)
    lvl = X.mean(2)
    lvl_rank = lvl.argsort(1).argsort(1) / (N - 1.0)
    lvl_dev = (lvl - lvl.mean(1, keepdims=True)) / (lvl.std(1, keepdims=True) + 1e-9)
    sd = X.std(2)
    sd_dev = (sd - sd.mean(1, keepdims=True)) / (sd.std(1, keepdims=True) + 1e-9)
    C = np.einsum("bik,bjk->bij", z, z) / K
    off = (C.sum(2) - 1.0) / (N - 1)
    res = []
    for b in range(B):
        Mx = X[b] - X[b].mean(1, keepdims=True)
        u, s, vt = np.linalg.svd(Mx, full_matrices=False)
        r = Mx - np.outer(u[:, 0] * s[0], vt[0])
        v = r.var(1) / (Mx.var(1) + 1e-9)
        res.append(v)
    res = np.stack(res)
    return np.stack([c_loo, lagged, lvl_dev, lvl_rank, sd_dev, off, res], -1)   # (B,N,7)


class HandRank:
    """One shared linear score per node, trained as a conditional logit."""
    def __init__(s): s.w = None

    def fit(s, X, y, epochs=200, lr=0.05):
        F = node_features(X)
        mu, sd = F.reshape(-1, F.shape[-1]).mean(0), F.reshape(-1, F.shape[-1]).std(0) + 1e-9
        s.mu, s.sd = mu, sd
        Ft = torch.tensor((F - mu) / sd, dtype=torch.float32)
        yt = torch.tensor(y, dtype=torch.long)
        w = torch.zeros(F.shape[-1], requires_grad=True)
        opt = torch.optim.Adam([w], lr=lr)
        for _ in range(epochs):
            opt.zero_grad()
            nn.functional.cross_entropy(Ft @ w, yt).backward()
            opt.step()
        s.w = w.detach()
        return s

    def score(s, X):
        F = (node_features(X) - s.mu) / s.sd
        return (torch.tensor(F, dtype=torch.float32) @ s.w).numpy()


def main():
    quick = "--quick" in sys.argv
    segs = [s for s in real_seg.segments() if len(s[0]) == NN and len(s[1]) == 1]
    print("N=%d one-hot segments: %d" % (NN, len(segs)), flush=True)
    res = json.load(open(RES)) if os.path.exists(RES) else {}
    cap = 60 if quick else 400
    epochs, patience = (3, 2) if quick else (25, 5)
    for mode in ("raw", "norm"):
        for seed in SEEDS if not quick else [0]:
            tr, va, te = split_segments(segs, seed)
            Xtr, ytr = make(tr, mode, cap, seed)
            Xva, yva = make(va, mode, cap, seed + 50)
            Xte, yte = make(te, mode, cap, seed + 90)
            key = "%s/seed%d" % (mode, seed)
            print("%s train %s val %s test %s (segments %d/%d/%d)"
                  % (key, Xtr.shape, Xva.shape, Xte.shape, len(tr), len(va), len(te)), flush=True)
            if res.get(key, {}).get("hand") is None:
                h = HandRank().fit(Xtr, ytr)
                res.setdefault(key, {})["hand"] = top1(h.score(Xte), yte)
                res[key]["chance"] = 1.0 / NN
                json.dump(res, open(RES, "w"), indent=1)
                print("   hand %.3f" % res[key]["hand"], flush=True)
            for rel in ("per-node", "deepsets", "relation", "attention"):
                if res.get(key, {}).get(rel) is not None:
                    continue
                t0 = time.time()
                net = fit_net(rel, Xtr, ytr, Xva, yva, 3e-4, epochs, patience)
                a = top1(predict(net, Xte), yte)
                res.setdefault(key, {})[rel] = a
                json.dump(res, open(RES, "w"), indent=1)
                print("   %-10s %.3f (%.1f min)" % (rel, a, (time.time() - t0) / 60), flush=True)
    print("done")


if __name__ == "__main__":
    main()
