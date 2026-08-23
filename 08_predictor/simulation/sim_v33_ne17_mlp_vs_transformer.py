"""
sim_v33_ne17_mlp_vs_transformer.py - NE17: Architecture-agnostic
capacity test (MLP vs Transformer).

v32 NE16 showed the U-curve for Transformer. v33 NE17 tests
whether the right-sized phenomenon is architecture-specific by
training MLPs at matched capacity points on PBFT MM hard regime.

MLP sizes (hidden_dim, n_layers):
  M1: 32x1   -> ~1K params
  M2: 64x2   -> ~5K params
  M3: 128x2  -> ~17K params (TinyTransformer match)
  M4: 256x2  -> ~67K params
  M5: 256x3  -> ~134K params (NE15 large Transformer match)
  M6: 512x3  -> ~530K params

3 seeds each. Same training regime as NE16 (Adam, 30 epochs, bs=64).
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
OUT = HERE / "v33_ne17_results"
OUT.mkdir(parents=True, exist_ok=True)

N_TR, N_TE, W = 1500, 500, 16
N_EPOCH = 30
LR = 1e-3
N_SEEDS = 3


MLP_SIZES = [
    ("M1_1K",   {"hidden": 32,  "layers": 1}),
    ("M2_5K",   {"hidden": 64,  "layers": 2}),
    ("M3_17K",  {"hidden": 128, "layers": 2}),
    ("M4_67K",  {"hidden": 256, "layers": 2}),
    ("M5_134K", {"hidden": 256, "layers": 3}),
    ("M6_530K", {"hidden": 512, "layers": 3}),
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


class MLP(nn.Module):
    def __init__(self, hidden, layers, input_dim=W):
        super().__init__()
        layers_list = [nn.Linear(input_dim, hidden), nn.ReLU(), nn.Dropout(0.1)]
        for _ in range(layers - 1):
            layers_list.extend([nn.Linear(hidden, hidden), nn.ReLU(), nn.Dropout(0.1)])
        layers_list.append(nn.Linear(hidden, 1))
        self.net = nn.Sequential(*layers_list)

    def forward(self, x):
        return self.net(x).squeeze(-1)


def train_eval_mlp(hidden, layers, seed):
    torch.manual_seed(seed * 131 + 7)
    legit_tr, byz_tr = gen_pbft_mm(N_TR)
    X = torch.from_numpy(np.vstack([legit_tr, byz_tr]).astype(np.float32))
    y = torch.from_numpy(np.concatenate([np.zeros(N_TR), np.ones(N_TR)]).astype(np.float32))
    perm = torch.randperm(len(X)); X, y = X[perm], y[perm]
    m = MLP(hidden, layers)
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
    print("=== NE17: MLP vs Transformer capacity comparison ===")
    rows = []
    for name, cfg in MLP_SIZES:
        aucs = []
        np_list = []
        for seed in range(N_SEEDS):
            np_count, auc = train_eval_mlp(cfg["hidden"], cfg["layers"], seed)
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
        })

    (OUT / "ne17.json").write_text(
        json.dumps(rows, indent=2), encoding="utf-8")

    # Plot MLP vs Transformer (load NE16 Transformer data)
    import matplotlib.pyplot as plt
    trf_rows = []
    try:
        trf_path = HERE / "v32_ne16_results" / "ne16.json"
        trf_rows = json.loads(trf_path.read_text())
    except Exception as e:
        print(f"  WARN: NE16 data not loaded: {e}")

    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    if trf_rows:
        trf_params = [r["n_params"] for r in trf_rows]
        trf_means = [r["auc_mean"] for r in trf_rows]
        trf_stds = [r["auc_std"] for r in trf_rows]
        ax.errorbar(trf_params, trf_means, yerr=trf_stds, fmt='o-',
                    color='#1f77b4', lw=1.6, capsize=4, markersize=7,
                    label='Transformer (NE16)')
    mlp_params = [r["n_params"] for r in rows]
    mlp_means = [r["auc_mean"] for r in rows]
    mlp_stds = [r["auc_std"] for r in rows]
    ax.errorbar(mlp_params, mlp_means, yerr=mlp_stds, fmt='s-',
                color='#d62728', lw=1.6, capsize=4, markersize=7,
                label='MLP (NE17, this paper)')
    ax.axhline(0.574, color='gray', ls=':', lw=1)
    ax.text(1.5e3, 0.585, 'fixed feature ceiling (0.574)',
            fontsize=8, color='gray')
    ax.axhline(0.5, color='red', ls=':', lw=1)
    ax.text(1.5e3, 0.515, 'Theorem 1 ceiling ($1/2$)',
            fontsize=8, color='red')
    ax.set_xscale('log')
    ax.set_xlabel('Number of parameters (log scale)')
    ax.set_ylabel('AUC on PBFT moment-matched (3 seeds, mean$\\pm$std)')
    ax.set_title('NE17: Architecture-agnostic capacity sweep --- MLP vs.\\ Transformer')
    ax.set_ylim(0.4, 1.05)
    ax.legend(loc='lower center', fontsize=9)
    ax.grid(True, alpha=0.3, which='both')
    plt.tight_layout()
    plt.savefig('figures/fig16_mlp_vs_transformer.pdf', dpi=300, bbox_inches='tight')
    plt.savefig('figures/fig16_mlp_vs_transformer.png', dpi=150, bbox_inches='tight')
    plt.close()

    md = ["# NE17: MLP vs Transformer Capacity Comparison\n"]
    md.append("MLP trained at 6 capacity points on PBFT MM, 3 seeds each.\n")
    md.append("| Size | params | AUC mean | AUC std | median | max |")
    md.append("|---|---:|---:|---:|---:|---:|")
    for r in rows:
        md.append(f"| {r['size_label']} | {r['n_params']:,} | "
                  f"{r['auc_mean']:.4f} | {r['auc_std']:.4f} | "
                  f"{r['auc_median']:.4f} | {r['auc_max']:.4f} |")
    (OUT / "REPORT.md").write_text("\n".join(md), encoding="utf-8")
    print(f"\nFigure: figures/fig16_mlp_vs_transformer.pdf")


if __name__ == "__main__":
    main()
