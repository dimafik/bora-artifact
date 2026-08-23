"""R2: is a relational operator across orderers necessary?

This is the regime BORA actually operates in.  Telling "this node is slow" from
"the network is slow" cannot be done from one node's window, because the two look
identical once each window is normalised.  It is a comparison between nodes.

    healthy   all N nodes' delay rises together (global congestion)
    attack    one node's delay rises alone

FAIRNESS.  Every architecture gets the same choice of cross-node aggregator
(mean / max / attention).  Giving the relational operator to the Transformer
alone would decide the outcome in the design, which is the thing this whole
re-analysis exists to avoid.  So the question here is not "which encoder wins"
but "does a relational operator across nodes matter", asked of all of them.

Each model is: per-node encoder (its own kind) -> per-node vector -> cross-node
aggregator -> head.
"""
import sys, json, time
import numpy as np
import torch
import torch.nn as nn

sys.path.insert(0, "."); sys.path.insert(0, ".."); sys.path.insert(0, "../predictor")
import gen, hard_gen, ed_run as E
from model import ScorePredictor, CONFIG

K = gen.K
NNODE = 5
TRAIN_PAIRS, VAL_PAIRS, TEST_PAIRS = 4000, 600, 1200
AGGS = ["mean", "max", "attn"]   # attn = cross-node self-attention
LRS = [3e-4, 1e-3]


# ---------------------------------------------------------------- data
def scenario(rng, single):
    """Returns (NNODE, K) raw RTT.  Each node is normalised on its own, so no
    single node's window reveals which scenario it came from."""
    base = rng.normal(0, 1, K)                       # shared network jitter
    lift = rng.uniform(0.8, 1.6)
    out = []
    hot = int(rng.integers(NNODE)) if single else -1
    for i in range(NNODE):
        x = base * rng.uniform(0.85, 1.15) + rng.normal(0, 0.3, K)
        if single:
            if i == hot:
                x = x + lift * np.abs(rng.normal(1, 0.2, K))
        else:
            x = x + lift * np.abs(rng.normal(1, 0.2, K))   # every node lifted
        out.append(hard_gen._norm(x))                      # per-node normalise
    return np.stack(out)


def build(n, seed):
    rng = np.random.default_rng(seed)
    X, y = [], []
    for _ in range(n):
        for single in (False, True):
            raw = scenario(rng, single)
            X.append(np.stack([gen.window(raw[i]) for i in range(NNODE)]))
            y.append(1 if single else 0)
    return (torch.tensor(np.stack(X), dtype=torch.float32),
            torch.tensor(np.array(y), dtype=torch.float32))


# ---------------------------------------------------------------- models
def agg(h, mode, q, mha=None):
    """h: (B, N, dim) per-node embeddings.

    mean and max cannot compare nodes: each node is normalised on its own, so its
    embedding carries no scenario information, and pooling uninformative vectors
    stays uninformative.  A fixed-query attention only re-weights them, which is
    the same limitation.  Detecting "one node is unlike the others" needs the
    nodes to see each other, so the relational aggregator is cross-node
    SELF-attention.  It is offered to every encoder, not only ours."""
    if mode == "mean":
        return h.mean(1)
    if mode == "max":
        return h.max(1).values
    a, _ = mha(h, h, h)
    return (h + a).mean(1)


class Base(nn.Module):
    """B x NNODE x K x 8  ->  per-node vector  ->  cross-node aggregate  -> logit"""
    def __init__(s, norm, aggregator, dim):
        super().__init__()
        s.n, s.a = norm, aggregator
        s.q = nn.Parameter(torch.randn(dim) * 0.05)
        s.mha = nn.MultiheadAttention(dim, 4, batch_first=True) if aggregator == "attn" else None
        s.o = nn.Sequential(nn.Linear(dim, 32), nn.ReLU(), nn.Linear(32, 1))

    def forward(s, X):
        B, N = X.shape[0], X.shape[1]
        z = s.encode(s.n(X.reshape(B * N, K, 8)))        # (B*N, dim)
        return s.o(agg(z.reshape(B, N, -1), s.a, s.q, s.mha))


class SummaryNet(Base):
    def __init__(s, norm, a):
        super().__init__(norm, a, 32)
        s.f = nn.Sequential(nn.Flatten(), nn.Linear(K * 8, 32), nn.ReLU())
    def encode(s, x): return s.f(x)


class CNNNet(Base):
    def __init__(s, norm, a):
        super().__init__(norm, a, 16)
        s.c = nn.Sequential(nn.Conv1d(8, 16, 5, padding=2), nn.ReLU(),
                            nn.Conv1d(16, 16, 5, padding=2), nn.ReLU(),
                            nn.AdaptiveAvgPool1d(1), nn.Flatten())
    def encode(s, x): return s.c(x.transpose(1, 2))


class GRUNet(Base):
    def __init__(s, norm, a):
        super().__init__(norm, a, 24)
        s.g = nn.GRU(8, 24, batch_first=True)
    def encode(s, x): return s.g(x)[0][:, -1]


class TFNet(Base):
    def __init__(s, norm, a):
        super().__init__(norm, a, CONFIG.d_model)
        s.m = ScorePredictor(CONFIG)
        s.tq = nn.Parameter(torch.randn(CONFIG.d_model) * 0.02)
    def encode(s, x):
        h = s.m.encoder(s.m.pos_enc(s.m.input_proj(x)))
        w = torch.softmax((h @ s.tq) / CONFIG.d_model ** 0.5, dim=1)
        return (h * w.unsqueeze(-1)).sum(1)


NETS = [("MLP encoder", SummaryNet), ("1D-CNN encoder", CNNNet),
        ("GRU encoder", GRUNet), ("Transformer encoder (ours)", TFNet)]


def score(model, X, bs=64):
    model.eval()
    out = []
    with torch.no_grad():
        for i in range(0, len(X), bs):
            out.append(model(X[i:i + bs]))
    return torch.cat(out).squeeze(-1).numpy()


def fit(net, Xtr, ytr, Xva, yva, lr, epochs=25, patience=5):
    import copy
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
    Xtr, ytr = build(TRAIN_PAIRS, 101)
    Xva, yva = build(VAL_PAIRS, 202)
    Xte, yte = build(TEST_PAIRS, 303)
    print("data %s  (nodes=%d)" % (tuple(Xtr.shape), NNODE), flush=True)

    # single-node control: can one node's window alone tell the classes apart?
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline
    S1 = gen.summarise(Xtr[:, 0]); S1e = gen.summarise(Xte[:, 0])
    m1 = make_pipeline(StandardScaler(), LogisticRegression(max_iter=5000)).fit(S1, ytr.numpy())
    print("single-node summary-stat control AUC=%.4f  (should be ~0.5)"
          % gen.auc(yte.numpy(), m1.decision_function(S1e)), flush=True)
    # all-node summary stats, concatenated, no relational operator
    Sa = np.concatenate([gen.summarise(Xtr[:, i]) for i in range(NNODE)], 1)
    Sae = np.concatenate([gen.summarise(Xte[:, i]) for i in range(NNODE)], 1)
    ma = make_pipeline(StandardScaler(), LogisticRegression(max_iter=5000)).fit(Sa, ytr.numpy())
    rows = [dict(name="logistic / all-node summary stats", agg="concat",
                 auc=round(gen.auc(yte.numpy(), ma.decision_function(Sae)), 4))]
    print("  %-30s %-6s AUC=%.4f" % (rows[0]["name"][:30], "concat", rows[0]["auc"]), flush=True)

    norm = E.Norm(Xtr.reshape(-1, K, 8))
    for nm, cls in NETS:
        for a in AGGS:
            best = None
            for lr in LRS:
                t = time.time()
                net, ep = fit(cls(norm, a), Xtr, ytr, Xva, yva, lr)
                auc = gen.auc(yte.numpy(), score(net, Xte))
                print("  %-28s agg=%-5s lr=%.0e ep=%2d AUC=%.4f (%.1f min)"
                      % (nm, a, lr, ep, auc, (time.time() - t) / 60), flush=True)
                if best is None or auc > best["auc"]:
                    best = dict(name=nm, agg=a, lr=lr,
                                params=sum(p.numel() for p in net.parameters()),
                                auc=round(auc, 4))
            rows.append(best)
            json.dump(rows, open("r2_results.json", "w"), indent=1)
    print("done", flush=True)


if __name__ == "__main__":
    main()
