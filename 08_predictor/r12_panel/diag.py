"""Ten-minute decisive check before committing to a full re-run.

Three faults were found in the previous comparison, two of them mine:

  1. the Transformer alone was denied the per-channel normalisation the MLP, CNN
     and GRU all received -- the same handicap that pinned the MLP at 0.51 until
     I fixed it for the baselines;
  2. ScorePredictor mean-pools the encoder output over time (z = h.mean(1)), so a
     5-25 step attack inside a 60 step window is averaged away.  That makes the
     architecture behave like a summary statistic, which is what we measured;
  3. H1 placed the attack at the END of the window, which exactly matches the
     GRU's last-hidden-state readout.  Benchmark bias in the GRU's favour.

This script fixes 1 and 3 and sweeps the readout for 2.  If the Transformer does
not move, the cause is elsewhere and a full re-run would be premature.
"""
import sys, time
import numpy as np, torch, torch.nn as nn
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, "."); sys.path.insert(0, ".."); sys.path.insert(0, "../predictor")
import gen, hard_gen, ed_run as E
from model import ScorePredictor, CONFIG


def partial_anywhere(rng, family, lo=5, hi=25):
    """H1 with the segment placed anywhere, not only at the end."""
    L = int(rng.integers(lo, hi + 1))
    s = int(rng.integers(0, gen.K - L + 1))
    a = hard_gen.attack(rng, family)
    x = rng.normal(0, 1, gen.K)
    x[s:s + L] = (a[s:s + L] - hard_gen.MEAN) / hard_gen.STD
    return hard_gen._norm(x)


def build_H1b(n, seed):
    rng = np.random.default_rng(seed)
    X, y = [], []
    for _ in range(n):
        X.append(gen.window(hard_gen.healthy(rng))); y.append(0)
        f = hard_gen.FAMILIES[rng.integers(4)]
        X.append(gen.window(partial_anywhere(rng, f))); y.append(1)
    return torch.tensor(np.stack(X)), torch.tensor(np.array(y), dtype=torch.float32)


class TF(nn.Module):
    """Same encoder, same weights count; only the readout changes."""
    def __init__(self, norm, readout):
        super().__init__()
        self.n, self.readout = norm, readout
        self.m = ScorePredictor(CONFIG)
        if readout == "attn":
            self.q = nn.Parameter(torch.randn(CONFIG.d_model) * 0.02)
        self.head = nn.Sequential(nn.Linear(CONFIG.d_model, 32), nn.ReLU(),
                                  nn.Linear(32, 1))

    def forward(self, X):
        h = self.m.encoder(self.m.pos_enc(self.m.input_proj(self.n(X))))
        if self.readout == "mean":
            z = h.mean(1)
        elif self.readout == "max":
            z = h.max(1).values
        else:
            w = torch.softmax((h @ self.q) / CONFIG.d_model ** 0.5, dim=1)
            z = (h * w.unsqueeze(-1)).sum(1)
        return self.head(z)


Xtr, ytr = build_H1b(10000, 101)
Xva, yva = build_H1b(1000, 202)
Xte, yte = build_H1b(2000, 303)
norm = E.Norm(Xtr)
print("H1b (공격 위치 무작위) — Transformer 판독 방식별\n", flush=True)
for readout in ("mean", "max", "attn"):
    for lr in (3e-4, 1e-3):
        t = time.time()
        net, ep = E.fit_torch(TF(norm, readout), Xtr, ytr, Xva, yva, 40, 6, lr=lr)
        a = gen.auc(yte.numpy(), E.score(net, Xte))
        print("  readout=%-5s lr=%.0e  ep=%2d  AUC=%.4f   (%.1f min)"
              % (readout, lr, ep, a, (time.time() - t) / 60), flush=True)
