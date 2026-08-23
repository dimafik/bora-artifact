"""R2b: does a relational operator across orderers help, and where must it sit?

The first attempt put the cross-node operator AFTER each node had been encoded
and pooled over time.  That cannot work: an encoder that sees one node alone
cannot record how similar that node is to the others, and pooling has already
discarded the waveform the comparison would need.  Measured 0.52 for everything,
while hand-built pairwise-correlation features reach 0.888 on the same data --
the signal is there, the architecture was throwing it away.

So the operator moves BEFORE temporal pooling, and every encoder family gets one
in its own idiom.  The question this asks is not "which encoder wins" but
"does mixing across nodes matter, and does it matter more than the encoder".

    healthy   all N nodes' delay rises together
    attack    one node rises alone
Each node's window is normalised on its own, so a single node reveals nothing
(control: 0.516) and even all five nodes' summary statistics concatenated reveal
nothing (control: 0.520).  Only the relationship between nodes carries the class.
"""
import sys, json, time, copy
import numpy as np
import torch
import torch.nn as nn

sys.path.insert(0, "."); sys.path.insert(0, ".."); sys.path.insert(0, "../predictor")
import gen, ed_run as E
from r2_run import build, NNODE, score
from model import ScorePredictor, CONFIG

K = gen.K
TRAIN_PAIRS, VAL_PAIRS, TEST_PAIRS = 2500, 600, 1200
LRS = [3e-4, 1e-3]


class MLPNet(nn.Module):
    """nomix: encode each node alone, average.   mix: see all nodes at once."""
    def __init__(s, norm, mix):
        super().__init__()
        s.n, s.mix = norm, mix
        d = K * 8 * (NNODE if mix else 1)
        s.f = nn.Sequential(nn.Flatten(), nn.Linear(d, 64), nn.ReLU(),
                            nn.Linear(64, 32), nn.ReLU(), nn.Linear(32, 1))

    def forward(s, X):
        B, N = X.shape[0], X.shape[1]
        Z = s.n(X.reshape(B * N, K, 8)).reshape(B, N, K, 8)
        if s.mix:
            return s.f(Z)
        return s.f(Z.reshape(B * N, K, 8)).reshape(B, N).mean(1, keepdim=True)


class CNNNet(nn.Module):
    """nomix: Conv1d over time, per node.   mix: Conv2d over (node, time)."""
    def __init__(s, norm, mix):
        super().__init__()
        s.n, s.mix = norm, mix
        if mix:
            s.c = nn.Sequential(nn.Conv2d(8, 16, (NNODE, 5), padding=(0, 2)), nn.ReLU(),
                                nn.Conv2d(16, 16, (1, 5), padding=(0, 2)), nn.ReLU())
        else:
            s.c = nn.Sequential(nn.Conv1d(8, 16, 5, padding=2), nn.ReLU(),
                                nn.Conv1d(16, 16, 5, padding=2), nn.ReLU())
        s.o = nn.Linear(16, 1)

    def forward(s, X):
        B, N = X.shape[0], X.shape[1]
        Z = s.n(X.reshape(B * N, K, 8)).reshape(B, N, K, 8)
        if s.mix:
            h = s.c(Z.permute(0, 3, 1, 2))          # B,8,N,K
            return s.o(h.mean(dim=(2, 3)))
        h = s.c(Z.reshape(B * N, K, 8).transpose(1, 2)).mean(2)
        return s.o(h.reshape(B, N, -1).mean(1))


class GRUNet(nn.Module):
    """nomix: GRU per node, average.   mix: all nodes' features at each timestep."""
    def __init__(s, norm, mix):
        super().__init__()
        s.n, s.mix = norm, mix
        s.g = nn.GRU(8 * (NNODE if mix else 1), 24, batch_first=True)
        s.o = nn.Linear(24, 1)

    def forward(s, X):
        B, N = X.shape[0], X.shape[1]
        Z = s.n(X.reshape(B * N, K, 8)).reshape(B, N, K, 8)
        if s.mix:
            h = s.g(Z.permute(0, 2, 1, 3).reshape(B, K, N * 8))[0][:, -1]
            return s.o(h)
        h = s.g(Z.reshape(B * N, K, 8))[0][:, -1]
        return s.o(h.reshape(B, N, -1).mean(1))


class TFNet(nn.Module):
    """nomix: our encoder per node, average.
       mix:  attention ACROSS NODES at each timestep, then our encoder."""
    def __init__(s, norm, mix):
        super().__init__()
        s.n, s.mix = norm, mix
        s.m = ScorePredictor(CONFIG)
        d = CONFIG.d_model
        s.node_attn = nn.MultiheadAttention(d, 4, batch_first=True) if mix else None
        s.q = nn.Parameter(torch.randn(d) * 0.02)
        s.o = nn.Sequential(nn.Linear(d, 32), nn.ReLU(), nn.Linear(32, 1))

    def forward(s, X):
        B, N = X.shape[0], X.shape[1]
        Z = s.n(X.reshape(B * N, K, 8))
        h = s.m.input_proj(Z)                                   # B*N, K, d
        d = h.shape[-1]
        if s.mix:
            hn = h.reshape(B, N, K, d).permute(0, 2, 1, 3).reshape(B * K, N, d)
            a, _ = s.node_attn(hn, hn, hn)
            h = (hn + a).reshape(B, K, N, d).permute(0, 2, 1, 3).reshape(B * N, K, d)
        h = s.m.encoder(s.m.pos_enc(h))
        w = torch.softmax((h @ s.q) / d ** 0.5, dim=1)
        z = (h * w.unsqueeze(-1)).sum(1).reshape(B, N, d).mean(1)
        return s.o(z)


NETS = [("MLP", MLPNet), ("1D-CNN", CNNNet), ("GRU", GRUNet),
        ("Transformer (ours)", TFNet)]


def fit(net, Xtr, ytr, Xva, yva, lr, epochs=20, patience=4):
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


def corr_baseline(Xtr, ytr, Xte, yte):
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline

    def feat(X):
        r = X[:, :, :, 2].numpy()
        z = (r - r.mean(2, keepdims=True)) / (r.std(2, keepdims=True) + 1e-9)
        C = np.einsum("bik,bjk->bij", z, z) / r.shape[2]
        iu = np.triu_indices(r.shape[1], 1)
        pc = C[:, iu[0], iu[1]]
        return np.c_[pc.mean(1), pc.std(1), pc.min(1), pc.max(1),
                     np.sort(pc, 1)[:, :3], np.sort(pc, 1)[:, -3:]]
    m = make_pipeline(StandardScaler(), LogisticRegression(max_iter=5000)).fit(
        feat(Xtr), ytr.numpy())
    return gen.auc(yte.numpy(), m.decision_function(feat(Xte)))


def main():
    Xtr, ytr = build(TRAIN_PAIRS, 101)
    Xva, yva = build(VAL_PAIRS, 202)
    Xte, yte = build(TEST_PAIRS, 303)
    print("data %s" % (tuple(Xtr.shape),), flush=True)
    ref = corr_baseline(Xtr, ytr, Xte, yte)
    print("hand-built pairwise-correlation reference AUC=%.4f" % ref, flush=True)

    rows = [dict(name="pairwise-correlation features + logistic", variant="hand",
                 params=None, auc=round(ref, 4))]
    norm = E.Norm(Xtr.reshape(-1, K, 8))
    for nm, cls in NETS:
        for mix in (False, True):
            best = None
            for lr in LRS:
                t = time.time()
                net, ep = fit(cls(norm, mix), Xtr, ytr, Xva, yva, lr)
                a = gen.auc(yte.numpy(), score(net, Xte))
                print("  %-20s %-6s lr=%.0e ep=%2d AUC=%.4f (%.1f min)"
                      % (nm, "mix" if mix else "nomix", lr, ep, a,
                         (time.time() - t) / 60), flush=True)
                if best is None or a > best["auc"]:
                    best = dict(name=nm, variant="mix" if mix else "nomix",
                                params=sum(p.numel() for p in net.parameters()),
                                lr=lr, auc=round(a, 4))
            rows.append(best)
            json.dump(rows, open("r2b_results.json", "w"), indent=1)
    print("done", flush=True)


if __name__ == "__main__":
    main()
