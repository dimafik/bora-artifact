"""D2: does the model survive a change of cluster size, and does node order matter?

The paper runs at N = 5, 7, 9, 11, 15, 21 and Section III-H covers joint-consensus
reconfiguration, so the orderer count changes while the system is live.  A model
whose input shape is tied to N is not a worse detector -- it is undeployable.
That is a different kind of claim from AUC and we never tested it.

Train at N=5 only.  Test at N = 5, 7, 9, 11, 21, and again with the node order
shuffled.  Orderers have no natural ordering, so any model that learns one is
relying on an artefact.

Fairness: the fixed-shape models are GIVEN an adaptation (adaptive pooling over
the node axis, or truncate/pad) rather than being declared impossible.  Whether
the adaptation holds up is the measurement.
"""
import sys, json, time, copy
import numpy as np
import torch
import torch.nn as nn

sys.path.insert(0, "."); sys.path.insert(0, ".."); sys.path.insert(0, "../predictor")
import gen, hard_gen, ed_run as E
from d1_run import build as build_attr

K = gen.K
TRAIN, VAL, TEST = 4000, 800, 1200
TEST_NS = [5, 7, 9, 11, 21]
LRS = [3e-4, 1e-3]
D = 32


def scenario(rng, n, single):
    base = rng.normal(0, 1, K)
    lift = rng.uniform(0.8, 1.6)
    hot = int(rng.integers(n)) if single else -1
    out = []
    for i in range(n):
        x = base * rng.uniform(0.85, 1.15) + rng.normal(0, 0.3, K)
        if (single and i == hot) or (not single):
            x = x + lift * np.abs(rng.normal(1, 0.2, K))
        out.append(hard_gen._norm(x))
    return np.stack(out)


def build(nsamp, seed, n):
    rng = np.random.default_rng(seed)
    X, y = [], []
    for _ in range(nsamp):
        for single in (False, True):
            raw = scenario(rng, n, single)
            X.append(np.stack([gen.window(raw[i]) for i in range(n)]))
            y.append(1 if single else 0)
    return (torch.tensor(np.stack(X), dtype=torch.float32),
            torch.tensor(np.array(y), dtype=torch.float32))


class Net(nn.Module):
    """Shared per-node encoder; only the cross-node operator differs.

    mlp-concat and conv2d are tied to the training N.  They are given an
    adaptation so they can be evaluated at other N at all: the node axis is
    adaptively pooled to the training width before the fixed part runs.  That is
    a real deployment option, not a straw man, and the measurement says whether
    it survives."""
    def __init__(s, norm, rel, ntrain=5):
        super().__init__()
        s.n, s.rel, s.ntrain = norm, rel, ntrain
        s.enc = nn.Sequential(nn.Conv1d(8, D, 5, padding=2), nn.ReLU(),
                              nn.Conv1d(D, D, 5, padding=2), nn.ReLU())
        if rel == "mlp-concat":
            s.mix = nn.Sequential(nn.Flatten(), nn.Linear(D * ntrain, 64), nn.ReLU())
            dim = 64
        elif rel == "conv2d":
            s.mix = nn.Conv2d(D, D, (ntrain, 1))
            dim = D
        elif rel == "gru-nodes":
            s.mix = nn.GRU(D, D // 2, batch_first=True, bidirectional=True)
            dim = D
        else:
            s.mix = nn.MultiheadAttention(D, 4, batch_first=True)
            dim = D
        s.o = nn.Sequential(nn.Linear(dim, 32), nn.ReLU(), nn.Linear(32, 1))

    def forward(s, X):
        B, N = X.shape[0], X.shape[1]
        h = s.enc(s.n(X.reshape(B * N, K, 8)).transpose(1, 2)).mean(2).reshape(B, N, D)
        if s.rel in ("mlp-concat", "conv2d") and N != s.ntrain:
            h = torch.nn.functional.adaptive_avg_pool1d(
                h.transpose(1, 2), s.ntrain).transpose(1, 2)      # the adaptation
        if s.rel == "mlp-concat":
            z = s.mix(h)
        elif s.rel == "conv2d":
            z = s.mix(h.permute(0, 2, 1).unsqueeze(-1)).squeeze(-1).squeeze(-1)
        elif s.rel == "gru-nodes":
            z = (h + s.mix(h)[0]).mean(1)
        else:
            z = (h + s.mix(h, h, h)[0]).mean(1)
        return s.o(z)


RELS = ["mlp-concat", "conv2d", "gru-nodes", "attention"]


def score(model, X, bs=64):
    model.eval()
    out = []
    with torch.no_grad():
        for i in range(0, len(X), bs):
            out.append(model(X[i:i + bs]))
    return torch.cat(out).squeeze(-1).numpy()


def fit(net, Xtr, ytr, Xva, yva, lr, epochs=25, patience=5):
    opt = torch.optim.Adam(net.parameters(), lr=lr)
    bce = nn.BCEWithLogitsLoss()
    best, state, bad = -1.0, None, 0
    for ep in range(epochs):
        net.train()
        perm = torch.randperm(len(Xtr))
        for i in range(0, len(Xtr), 32):
            idx = perm[i:i + 32]
            opt.zero_grad()
            bce(net(Xtr[idx]).squeeze(-1), ytr[idx]).backward()
            opt.step()
        a = gen.auc(yva.numpy(), score(net, Xva))
        if a > best + 1e-4:
            best, state, bad = a, copy.deepcopy(net.state_dict()), 0
        else:
            bad += 1
            if bad >= patience:
                break
    net.load_state_dict(state); net.eval()
    return net, ep + 1


def main():
    Xtr, ytr = build(TRAIN, 101, 5)
    Xva, yva = build(VAL, 202, 5)
    tests = {n: build(TEST, 300 + n, n) for n in TEST_NS}
    print("train N=5 %s ; test N=%s" % (tuple(Xtr.shape), TEST_NS), flush=True)
    norm = E.Norm(Xtr.reshape(-1, K, 8))
    rows = []
    for rel in RELS:
        best = None
        for lr in LRS:
            t = time.time()
            net, ep = fit(Net(norm, rel), Xtr, ytr, Xva, yva, lr)
            aucs, shuf = {}, {}
            for n, (Xe, ye) in tests.items():
                aucs[n] = round(gen.auc(ye.numpy(), score(net, Xe)), 4)
                g = torch.Generator().manual_seed(0)
                Xp = torch.stack([Xe[i][torch.randperm(n, generator=g)]
                                  for i in range(len(Xe))])
                shuf[n] = round(gen.auc(ye.numpy(), score(net, Xp)), 4)
            print("  %-11s lr=%.0e ep=%2d  " % (rel, lr, ep)
                  + " ".join("N%d=%.3f" % (n, aucs[n]) for n in TEST_NS)
                  + "  | shuffled N5=%.3f N21=%.3f  (%.1f min)"
                  % (shuf[5], shuf[21], (time.time() - t) / 60), flush=True)
            if best is None or aucs[5] > best["auc"][5]:
                best = dict(rel=rel, lr=lr, auc=aucs, shuffled=shuf,
                            params=sum(p.numel() for p in net.parameters()))
        rows.append(best)
        json.dump(rows, open("d2_results.json", "w"), indent=1)
    print("done", flush=True)


if __name__ == "__main__":
    main()
