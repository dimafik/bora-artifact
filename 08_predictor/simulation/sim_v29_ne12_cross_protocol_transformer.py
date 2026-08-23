"""
sim_v29_ne12_cross_protocol_transformer.py - NE12: Transformer
applied to all 3 protocol MM variants (PBFT, HotStuff, Tendermint).
"""
from __future__ import annotations
import json
import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import roc_auc_score
from pathlib import Path

torch.manual_seed(20260630)
rng = np.random.default_rng(20260630)
HERE = Path(__file__).parent
OUT = HERE / "v29_ne12_results"
OUT.mkdir(parents=True, exist_ok=True)

N_TRAIN = 1500
N_TEST = 500
W = 16
N_EPOCHS = 40
LR = 1e-3
D_MODEL = 32
N_HEAD = 4
N_LAYER = 2
FFN = 64


def gen_pbft_mm(n):
    legit = rng.normal(0.5, 0.1, (n, W))
    byz = rng.normal(0.5, 0.1, (n, W))
    for i in range(n):
        n_burst = rng.integers(3, 6)
        pos = rng.choice(W, n_burst, replace=False)
        byz[i, pos] = 1.5
        other = [j for j in range(W) if j not in pos]
        excess = np.sum(byz[i, pos]) - n_burst * np.mean(legit)
        byz[i, other] -= excess / len(other)
        tv = np.var(legit[i]); cv = np.var(byz[i])
        if cv > 0:
            byz[i] = ((byz[i] - np.mean(byz[i])) *
                      np.sqrt(tv / cv) + np.mean(byz[i]))
    return legit, byz


def gen_hotstuff_mm(n):
    legit = rng.normal(1.0, 0.05, (n, W))
    byz = rng.normal(1.0, 0.05, (n, W))
    for i in range(n):
        lag = rng.integers(2, 8)
        decay = np.linspace(0, 0.4, W - lag)
        byz[i, lag:] -= decay
        n_pre = lag
        if n_pre > 0:
            byz[i, :lag] += np.sum(decay) / n_pre
        m_tgt, v_tgt = np.mean(legit[i]), np.var(legit[i])
        cm, cv = np.mean(byz[i]), np.var(byz[i])
        if cv > 0:
            byz[i] = ((byz[i] - cm) *
                      np.sqrt(v_tgt / cv) + m_tgt)
    return legit, byz


def gen_tendermint_mm(n):
    legit = rng.normal(0.9, 0.05, (n, W))
    byz = rng.normal(0.9, 0.05, (n, W))
    for i in range(n):
        n_drops = rng.integers(2, 4)
        pos = rng.choice(W, n_drops, replace=False)
        byz[i, pos] = 0.3
        other = [j for j in range(W) if j not in pos]
        deficit = n_drops * (np.mean(legit) - 0.3)
        byz[i, other] += deficit / len(other)
        tv = np.var(legit[i]); cv = np.var(byz[i])
        if cv > 0:
            byz[i] = ((byz[i] - np.mean(byz[i])) *
                      np.sqrt(tv / cv) + np.mean(byz[i]))
    return legit, byz


class PE(nn.Module):
    def __init__(self, d, m=64):
        super().__init__()
        pe = torch.zeros(m, d)
        pos = torch.arange(m).unsqueeze(1).float()
        div = torch.exp(torch.arange(0, d, 2).float() *
                        (-np.log(10000.0) / d))
        pe[:, 0::2] = torch.sin(pos * div)
        pe[:, 1::2] = torch.cos(pos * div)
        self.register_buffer("pe", pe)
    def forward(self, x): return x + self.pe[: x.size(1)]


class Trf(nn.Module):
    def __init__(self):
        super().__init__()
        self.proj = nn.Linear(1, D_MODEL)
        self.pe = PE(D_MODEL)
        layer = nn.TransformerEncoderLayer(
            d_model=D_MODEL, nhead=N_HEAD, dim_feedforward=FFN,
            batch_first=True, dropout=0.1)
        self.enc = nn.TransformerEncoder(layer, N_LAYER)
        self.head = nn.Linear(D_MODEL, 1)
    def forward(self, x):
        x = x.unsqueeze(-1)
        x = self.proj(x); x = self.pe(x); x = self.enc(x)
        return self.head(x.mean(dim=1)).squeeze(-1)


def run_protocol(name, gen_fn, n_seeds=3):
    aucs = []
    for seed in range(n_seeds):
        torch.manual_seed(seed * 31 + 7)
        legit_tr, byz_tr = gen_fn(N_TRAIN)
        X_tr = torch.from_numpy(np.vstack([legit_tr, byz_tr]).astype(np.float32))
        y_tr = torch.from_numpy(np.concatenate([np.zeros(N_TRAIN), np.ones(N_TRAIN)]).astype(np.float32))
        perm = torch.randperm(len(X_tr))
        X_tr, y_tr = X_tr[perm], y_tr[perm]
        model = Trf()
        opt = torch.optim.Adam(model.parameters(), lr=LR)
        bce = nn.BCEWithLogitsLoss()
        bs = 64
        for ep in range(N_EPOCHS):
            model.train()
            p = torch.randperm(len(X_tr))
            for s in range(0, len(p), bs):
                idx = p[s:s+bs]
                opt.zero_grad()
                bce(model(X_tr[idx]), y_tr[idx]).backward(); opt.step()
        legit_te, byz_te = gen_fn(N_TEST)
        X_te = torch.from_numpy(np.vstack([legit_te, byz_te]).astype(np.float32))
        y_te = torch.from_numpy(np.concatenate([np.zeros(N_TEST), np.ones(N_TEST)]).astype(np.float32))
        model.eval()
        with torch.no_grad():
            auc = roc_auc_score(y_te.numpy(), model(X_te).numpy())
        aucs.append(float(auc))
        print(f"  [{name}] seed {seed}: AUC={auc:.4f}")
    return aucs


def main():
    print("=== NE12: Transformer cross-protocol MM sweep ===")
    out = {}
    for name, gen in [("PBFT_MM", gen_pbft_mm),
                      ("HotStuff_MM", gen_hotstuff_mm),
                      ("Tendermint_MM", gen_tendermint_mm)]:
        aucs = run_protocol(name, gen)
        out[name] = {
            "AUC_mean": float(np.mean(aucs)),
            "AUC_std": float(np.std(aucs)),
            "AUC_min": float(np.min(aucs)),
            "AUC_max": float(np.max(aucs)),
            "n_seeds": len(aucs),
        }
        print(f"  {name}: mean={out[name]['AUC_mean']:.4f}  std={out[name]['AUC_std']:.4f}")

    (OUT / "ne12.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    md = ["# NE12: Transformer Cross-Protocol MM Sweep\n"]
    md.append("3 seeds per protocol, encoder Transformer.\n")
    md.append("| Protocol | AUC mean | AUC std | min | max |")
    md.append("|---|---:|---:|---:|---:|")
    for k, v in out.items():
        md.append(f"| {k} | {v['AUC_mean']:.4f} | {v['AUC_std']:.4f} | {v['AUC_min']:.4f} | {v['AUC_max']:.4f} |")
    (OUT / "REPORT.md").write_text("\n".join(md), encoding="utf-8")


if __name__ == "__main__":
    main()
