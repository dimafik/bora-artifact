"""D1: attribution -- which orderer is the degraded one?

Four rounds of experiments measured binary window classification.  The deployed
daemon does not emit a binary decision; it emits a SET OF NODE IDS:

    Bt=[3] r=0 cap=2

Algorithm 1's output is that set, and a false positive means excluding the wrong
orderer from candidacy -- the cost experiment #9 measured (159 forced leader
changes when the Active-Leader Rule is removed).  A detector with AUC 1.000 that
names the wrong node is useless here.  This is the axis we never measured.

Task: N=5 nodes share a common jitter, exactly ONE is degraded (extra
decorrelated noise).  Each node's window is normalised on its own, so no node
can be judged alone.  Output: which node.  Chance = 0.20.

Every model produces per-node scores.  What differs is how, and whether the
relational operator preserves node identity:

    per-node        no relation at all               (control, should fail)
    mean-deviation  subtract the cross-node mean      (hand-built, no learning)
    conv2d          mixes neighbouring nodes only     (assumes node ordering)
    gru-nodes       sequential over the node axis     (assumes node ordering)
    attention       all pairs, order-free             (ours)

Orderers have no natural ordering, so conv2d and gru-nodes are assuming
structure that does not exist.  Whether that costs them is part of the question.
"""
import sys, json, time, copy
import numpy as np
import torch
import torch.nn as nn

sys.path.insert(0, "."); sys.path.insert(0, ".."); sys.path.insert(0, "../predictor")
import gen, hard_gen, ed_run as E
from model import ScorePredictor, CONFIG

K = gen.K
NNODE = 5
TRAIN, VAL, TEST = 6000, 1000, 2000
LRS = [3e-4, 1e-3]
D = 32


def scenario(rng, n=NNODE):
    """Common jitter across nodes; exactly one node carries extra decorrelated
    noise.  Per-node normalisation hides it from any single-node view."""
    base = rng.normal(0, 1, K)
    hot = int(rng.integers(n))
    lift = rng.uniform(0.9, 1.7)
    out = []
    for i in range(n):
        x = base * rng.uniform(0.85, 1.15) + rng.normal(0, 0.3, K)
        if i == hot:
            x = x + lift * np.abs(rng.normal(1, 0.2, K))
        out.append(hard_gen._norm(x))
    return np.stack(out), hot


def build(nsamp, seed, n=NNODE):
    rng = np.random.default_rng(seed)
    X, y = [], []
    for _ in range(nsamp):
        raw, hot = scenario(rng, n)
        X.append(np.stack([gen.window(raw[i]) for i in range(n)]))
        y.append(hot)
    return (torch.tensor(np.stack(X), dtype=torch.float32),
            torch.tensor(np.array(y), dtype=torch.long))


class Attributor(nn.Module):
    """B,N,K,8 -> per-node logit.  `rel` selects the relational operator."""
    def __init__(s, norm, rel):
        super().__init__()
        s.n, s.rel = norm, rel
        s.enc = nn.Sequential(nn.Conv1d(8, D, 5, padding=2), nn.ReLU(),
                              nn.Conv1d(D, D, 5, padding=2), nn.ReLU())
        if rel == "conv2d":
            s.mix = nn.Conv2d(D, D, (3, 1), padding=(1, 0))
        elif rel == "gru-nodes":
            s.mix = nn.GRU(D, D // 2, batch_first=True, bidirectional=True)
        elif rel == "attention":
            s.mix = nn.MultiheadAttention(D, 4, batch_first=True)
        else:
            s.mix = None
        s.o = nn.Sequential(nn.Linear(D, 32), nn.ReLU(), nn.Linear(32, 1))

    def forward(s, X):
        B, N = X.shape[0], X.shape[1]
        Z = s.n(X.reshape(B * N, K, 8))
        if s.rel == "mean-dev":
            Z = (Z.reshape(B, N, K, 8) -
                 Z.reshape(B, N, K, 8).mean(1, keepdim=True)).reshape(B * N, K, 8)
        h = s.enc(Z.transpose(1, 2)).mean(2).reshape(B, N, D)     # per-node vec
        if s.rel == "conv2d":
            h = h + s.mix(h.permute(0, 2, 1).unsqueeze(-1)).squeeze(-1).permute(0, 2, 1)
        elif s.rel == "gru-nodes":
            h = h + s.mix(h)[0]
        elif s.rel == "attention":
            h = h + s.mix(h, h, h)[0]
        return s.o(h).squeeze(-1)                                  # B,N logits


RELS = ["per-node", "mean-dev", "conv2d", "gru-nodes", "attention"]


def top1(model, X, y, bs=128):
    model.eval()
    ok = 0
    with torch.no_grad():
        for i in range(0, len(X), bs):
            ok += (model(X[i:i + bs]).argmax(1) == y[i:i + bs]).sum().item()
    return ok / len(X)


def fit(net, Xtr, ytr, Xva, yva, lr, epochs=30, patience=5):
    opt = torch.optim.Adam(net.parameters(), lr=lr)
    ce = nn.CrossEntropyLoss()
    best, state, bad = -1.0, None, 0
    for ep in range(epochs):
        net.train()
        perm = torch.randperm(len(Xtr))
        for i in range(0, len(Xtr), 64):
            idx = perm[i:i + 64]
            opt.zero_grad()
            ce(net(Xtr[idx]), ytr[idx]).backward()
            opt.step()
        a = top1(net, Xva, yva)
        if a > best + 1e-4:
            best, state, bad = a, copy.deepcopy(net.state_dict()), 0
        else:
            bad += 1
            if bad >= patience:
                break
    net.load_state_dict(state); net.eval()
    return net, ep + 1


def main():
    Xtr, ytr = build(TRAIN, 101)
    Xva, yva = build(VAL, 202)
    Xte, yte = build(TEST, 303)
    print("data %s  chance=%.2f" % (tuple(Xtr.shape), 1.0 / NNODE), flush=True)
    norm = E.Norm(Xtr.reshape(-1, K, 8))
    rows = []
    for rel in RELS:
        best = None
        for lr in LRS:
            t = time.time()
            net, ep = fit(Attributor(norm, rel), Xtr, ytr, Xva, yva, lr)
            a = top1(net, Xte, yte)
            # permutation test: shuffle node order at test time
            g = torch.Generator().manual_seed(0)
            perm = torch.stack([torch.randperm(NNODE, generator=g) for _ in range(len(Xte))])
            Xp = torch.stack([Xte[i][perm[i]] for i in range(len(Xte))])
            yp = torch.stack([(perm[i] == yte[i]).nonzero()[0, 0] for i in range(len(Xte))])
            ap = top1(net, Xp, yp)
            print("  %-11s lr=%.0e ep=%2d  top1=%.4f  shuffled=%.4f  (%.1f min)"
                  % (rel, lr, ep, a, ap, (time.time() - t) / 60), flush=True)
            if best is None or a > best["top1"]:
                best = dict(rel=rel, lr=lr, top1=round(a, 4), shuffled=round(ap, 4),
                            params=sum(p.numel() for p in net.parameters()))
        rows.append(best)
        json.dump(rows, open("d1_results.json", "w"), indent=1)
    print("done", flush=True)


if __name__ == "__main__":
    main()
