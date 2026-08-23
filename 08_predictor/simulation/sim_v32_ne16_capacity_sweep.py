"""
sim_v32_ne16_capacity_sweep.py - NE16: Capacity sweep U-curve.

Train Transformer at 6 different sizes on PBFT MM hard regime to
plot the empirical AUC-vs-capacity curve. v31 only had 2 points
(17K, 270K). v32 fills in the curve to validate the "right-sized
architecture" finding with a continuous empirical relationship.

Sizes (d_model, n_layer, n_head, ffn):
  S1: 16, 1, 2, 32    -> ~5K params
  S2: 32, 2, 4, 64    -> ~17K params (TinyTransformer baseline)
  S3: 48, 2, 4, 96    -> ~50K params
  S4: 64, 3, 4, 128   -> ~120K params
  S5: 64, 4, 8, 128   -> ~270K params
  S6: 96, 4, 8, 192   -> ~580K params

3 seeds per size for variance.
"""
from __future__ import annotations
import json
import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import roc_auc_score
from pathlib import Path

torch.manual_seed(20260606)
rng = np.random.default_rng(20260606)
HERE = Path(__file__).parent
OUT = HERE / "v32_ne16_results"
OUT.mkdir(parents=True, exist_ok=True)

N_TR, N_TE, W = 1500, 500, 16
N_EPOCH = 30
LR = 1e-3
N_SEEDS = 3

SIZES = [
    ("S1_5K",   {"d": 16, "L": 1, "H": 2, "F": 32}),
    ("S2_17K",  {"d": 32, "L": 2, "H": 4, "F": 64}),
    ("S3_50K",  {"d": 48, "L": 2, "H": 4, "F": 96}),
    ("S4_120K", {"d": 64, "L": 3, "H": 4, "F": 128}),
    ("S5_270K", {"d": 64, "L": 4, "H": 8, "F": 128}),
    ("S6_580K", {"d": 96, "L": 4, "H": 8, "F": 192}),
]


def gen_pbft_mm(n):
    legit = rng.normal(0.5, 0.1, (n, W))
    byz = rng.normal(0.5, 0.1, (n, W))
    for i in range(n):
        nb = rng.integers(3, 6)
        pos = rng.choice(W, nb, replace=False)
        byz[i, pos] = 1.5
        other = [j for j in range(W) if j not in pos]
        excess = np.sum(byz[i, pos]) - nb * np.mean(legit)
        byz[i, other] -= excess / len(other)
        tv = np.var(legit[i]); cv = np.var(byz[i])
        if cv > 0:
            byz[i] = (byz[i] - np.mean(byz[i])) * np.sqrt(tv/cv) + np.mean(byz[i])
    return legit, byz


class PE(nn.Module):
    def __init__(self, d, m=64):
        super().__init__()
        pe = torch.zeros(m, d)
        pos = torch.arange(m).unsqueeze(1).float()
        div = torch.exp(torch.arange(0, d, 2).float() * (-np.log(10000.0)/d))
        pe[:, 0::2] = torch.sin(pos * div)
        pe[:, 1::2] = torch.cos(pos * div)
        self.register_buffer("pe", pe)
    def forward(self, x): return x + self.pe[: x.size(1)]


class TrfSize(nn.Module):
    def __init__(self, d, L, H, F):
        super().__init__()
        self.proj = nn.Linear(1, d)
        self.pe = PE(d)
        layer = nn.TransformerEncoderLayer(
            d_model=d, nhead=H, dim_feedforward=F,
            batch_first=True, dropout=0.1)
        self.enc = nn.TransformerEncoder(layer, L)
        self.head = nn.Linear(d, 1)
    def forward(self, x):
        x = x.unsqueeze(-1)
        x = self.proj(x); x = self.pe(x); x = self.enc(x)
        return self.head(x.mean(dim=1)).squeeze(-1)


def train_eval(d, L, H, F, seed):
    torch.manual_seed(seed * 131 + 7)
    legit_tr, byz_tr = gen_pbft_mm(N_TR)
    X = torch.from_numpy(np.vstack([legit_tr, byz_tr]).astype(np.float32))
    y = torch.from_numpy(np.concatenate([np.zeros(N_TR), np.ones(N_TR)]).astype(np.float32))
    perm = torch.randperm(len(X)); X, y = X[perm], y[perm]
    m = TrfSize(d, L, H, F)
    n_params = sum(p.numel() for p in m.parameters())
    opt = torch.optim.Adam(m.parameters(), lr=LR)
    bce = nn.BCEWithLogitsLoss()
    bs = 64
    for ep in range(N_EPOCH):
        m.train(); p = torch.randperm(len(X))
        for s in range(0, len(p), bs):
            idx = p[s:s+bs]; opt.zero_grad()
            bce(m(X[idx]), y[idx]).backward(); opt.step()
    legit_te, byz_te = gen_pbft_mm(N_TE)
    Xte = torch.from_numpy(np.vstack([legit_te, byz_te]).astype(np.float32))
    yte = np.concatenate([np.zeros(N_TE), np.ones(N_TE)])
    m.eval()
    with torch.no_grad():
        auc = roc_auc_score(yte, m(Xte).numpy())
    return n_params, float(auc)


def main():
    print("=== NE16: Capacity sweep U-curve on PBFT MM ===")
    rows = []
    for name, cfg in SIZES:
        aucs = []
        np_list = []
        for seed in range(N_SEEDS):
            np_count, auc = train_eval(cfg["d"], cfg["L"], cfg["H"], cfg["F"], seed)
            aucs.append(auc); np_list.append(np_count)
            print(f"  [{name}] params={np_count}  seed{seed}: AUC={auc:.4f}")
        rows.append({
            "size_label": name,
            "config": cfg,
            "n_params": int(np_list[0]),
            "auc_mean": float(np.mean(aucs)),
            "auc_std": float(np.std(aucs)),
            "auc_median": float(np.median(aucs)),
            "auc_max": float(np.max(aucs)),
            "auc_min": float(np.min(aucs)),
            "n_seeds": N_SEEDS,
        })

    (OUT / "ne16.json").write_text(
        json.dumps(rows, indent=2), encoding="utf-8")

    # Plot the U-curve
    import matplotlib.pyplot as plt
    params = [r["n_params"] for r in rows]
    means = [r["auc_mean"] for r in rows]
    stds = [r["auc_std"] for r in rows]
    medians = [r["auc_median"] for r in rows]
    maxs = [r["auc_max"] for r in rows]

    fig, ax = plt.subplots(figsize=(7.0, 3.6))
    ax.errorbar(params, means, yerr=stds, fmt='o-', color='#1f77b4',
                lw=1.5, capsize=4, markersize=7, label=f'mean$\\pm$std ({N_SEEDS} seeds)')
    ax.plot(params, medians, 's--', color='#ff7f0e', lw=1.2, markersize=6,
            label='median')
    ax.plot(params, maxs, '^:', color='#2ca02c', lw=1, markersize=5,
            label='best seed (max)')
    ax.axhline(0.574, color='gray', ls=':', lw=1)
    ax.text(params[0]*0.8, 0.585, 'fixed feature ceiling (0.574)',
            fontsize=8, color='gray')
    ax.axhline(0.5, color='red', ls=':', lw=1)
    ax.text(params[0]*0.8, 0.515, 'Theorem 1 ceiling ($1/2$)',
            fontsize=8, color='red')
    # Highlight right-sized
    rs_idx = 1  # S2_17K is the right-sized one
    ax.scatter([params[rs_idx]], [means[rs_idx]], s=180, marker='o',
               facecolor='none', edgecolor='#d62728', linewidth=2,
               label='right-sized (17K-param TinyTransformer)')
    ax.set_xscale('log')
    ax.set_xlabel('Number of Transformer parameters (log scale)')
    ax.set_ylabel('AUC on PBFT moment-matched (hard regime)')
    ax.set_title('NE16: Capacity Sweep U-curve --- ``right-sized\'\' minimum sufficient class')
    ax.set_ylim(0.4, 1.05)
    ax.legend(loc='lower center', fontsize=8, ncol=2)
    ax.grid(True, alpha=0.3, which='both')
    plt.tight_layout()
    plt.savefig('figures/fig15_capacity_sweep.pdf', dpi=300, bbox_inches='tight')
    plt.savefig('figures/fig15_capacity_sweep.png', dpi=150, bbox_inches='tight')
    plt.close()

    md = ["# NE16: Capacity Sweep U-curve\n"]
    md.append("Transformer trained at 6 capacity points on PBFT MM, 3 seeds each.\n")
    md.append("| Size | params | AUC mean | AUC std | median | max |")
    md.append("|---|---:|---:|---:|---:|---:|")
    for r in rows:
        md.append(f"| {r['size_label']} | {r['n_params']:,} | "
                  f"{r['auc_mean']:.4f} | {r['auc_std']:.4f} | "
                  f"{r['auc_median']:.4f} | {r['auc_max']:.4f} |")
    (OUT / "REPORT.md").write_text("\n".join(md), encoding="utf-8")
    print(f"\nFigure saved: figures/fig15_capacity_sweep.pdf")


if __name__ == "__main__":
    main()
