"""
sim_v30_ne15_ensemble_best.py - NE15: Best-result push.

Combines two pushes:
  (a) Larger Transformer (d=64, 4 layers, 8 heads) with multi-seed
      averaging across PBFT/HotStuff/Tendermint MM
  (b) Ensemble detector: Transformer + AR(1) + spike-aware,
      ensembled by logistic regression, on PBFT MM hard regime.

Goal: push all numbers as close to AUC=1.000 as possible.
"""
from __future__ import annotations
import json
import numpy as np
import torch
import torch.nn as nn
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from pathlib import Path

torch.manual_seed(20260702)
rng = np.random.default_rng(20260702)
HERE = Path(__file__).parent
OUT = HERE / "v30_ne15_results"
OUT.mkdir(parents=True, exist_ok=True)

N_TR, N_TE, W = 2000, 800, 16
EPOCHS = 60
LR = 1e-3
D_MODEL = 64
N_HEAD = 8
N_LAYER = 4
FFN = 128


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


def gen_hotstuff_mm(n):
    legit = rng.normal(1.0, 0.05, (n, W))
    byz = rng.normal(1.0, 0.05, (n, W))
    for i in range(n):
        lag = rng.integers(2, 8)
        decay = np.linspace(0, 0.4, W - lag)
        byz[i, lag:] -= decay
        if lag > 0:
            byz[i, :lag] += np.sum(decay) / lag
        tv = np.var(legit[i]); cv = np.var(byz[i])
        if cv > 0:
            byz[i] = (byz[i] - np.mean(byz[i])) * np.sqrt(tv/cv) + np.mean(legit[i])
    return legit, byz


def gen_tendermint_mm(n):
    legit = rng.normal(0.9, 0.05, (n, W))
    byz = rng.normal(0.9, 0.05, (n, W))
    for i in range(n):
        nd = rng.integers(2, 4)
        pos = rng.choice(W, nd, replace=False)
        byz[i, pos] = 0.3
        other = [j for j in range(W) if j not in pos]
        byz[i, other] += nd * (np.mean(legit) - 0.3) / len(other)
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


class BigTrf(nn.Module):
    def __init__(self):
        super().__init__()
        self.proj = nn.Linear(1, D_MODEL)
        self.pe = PE(D_MODEL)
        layer = nn.TransformerEncoderLayer(
            d_model=D_MODEL, nhead=N_HEAD, dim_feedforward=FFN,
            batch_first=True, dropout=0.1, activation='gelu')
        self.enc = nn.TransformerEncoder(layer, N_LAYER)
        self.head = nn.Sequential(
            nn.LayerNorm(D_MODEL), nn.Linear(D_MODEL, 64),
            nn.GELU(), nn.Dropout(0.1), nn.Linear(64, 1))
    def forward(self, x):
        x = x.unsqueeze(-1)
        x = self.proj(x); x = self.pe(x); x = self.enc(x)
        return self.head(x.mean(dim=1)).squeeze(-1)


def train_trf(legit, byz, epochs=EPOCHS):
    X = np.vstack([legit, byz]).astype(np.float32)
    y = np.concatenate([np.zeros(len(legit)), np.ones(len(byz))]).astype(np.float32)
    perm = rng.permutation(len(X))
    X, y = X[perm], y[perm]
    Xt = torch.from_numpy(X); yt = torch.from_numpy(y)
    m = BigTrf(); opt = torch.optim.AdamW(m.parameters(), lr=LR, weight_decay=1e-4)
    sch = torch.optim.lr_scheduler.OneCycleLR(
        opt, max_lr=LR*5, total_steps=epochs * (len(X)//64 + 1))
    bce = nn.BCEWithLogitsLoss()
    bs = 64
    for ep in range(epochs):
        m.train()
        p = torch.randperm(len(Xt))
        for s in range(0, len(p), bs):
            idx = p[s:s+bs]
            opt.zero_grad()
            bce(m(Xt[idx]), yt[idx]).backward()
            torch.nn.utils.clip_grad_norm_(m.parameters(), 1.0)
            opt.step(); sch.step()
    return m


def eval_trf(m, legit, byz):
    X = torch.from_numpy(np.vstack([legit, byz]).astype(np.float32))
    y = np.concatenate([np.zeros(len(legit)), np.ones(len(byz))])
    m.eval()
    with torch.no_grad():
        return float(roc_auc_score(y, m(X).numpy()))


def fixed_features(X):
    """compute (mean, std, kurtosis, lag1, spike_count, range_iqr)."""
    m = X.mean(axis=1, keepdims=True); v = X.var(axis=1, keepdims=True) + 1e-9
    Xc = X - m
    kurt = ((Xc**4).mean(axis=1, keepdims=True)) / (v**2) - 3
    lag1 = (Xc[:, :-1] * Xc[:, 1:]).sum(axis=1, keepdims=True) / (Xc**2).sum(axis=1, keepdims=True)
    spike = (np.abs(Xc) > 2 * np.sqrt(v)).sum(axis=1, keepdims=True)
    iqr = np.percentile(X, 75, axis=1, keepdims=True) - np.percentile(X, 25, axis=1, keepdims=True) + 1e-9
    rng_iqr = (X.max(axis=1, keepdims=True) - X.min(axis=1, keepdims=True)) / iqr
    return np.hstack([m, np.sqrt(v), kurt, lag1, spike, rng_iqr])


def run_cross_protocol():
    """Bigger Transformer on PBFT/HotStuff/Tendermint, 5 seeds."""
    out = {}
    for name, gen in [("PBFT_MM", gen_pbft_mm), ("HotStuff_MM", gen_hotstuff_mm), ("Tendermint_MM", gen_tendermint_mm)]:
        aucs = []
        for seed in range(5):
            torch.manual_seed(seed * 137 + 7)
            np.random.seed(seed * 137 + 7)
            legit_tr, byz_tr = gen(N_TR)
            m = train_trf(legit_tr, byz_tr, epochs=50)
            legit_te, byz_te = gen(N_TE)
            auc = eval_trf(m, legit_te, byz_te)
            aucs.append(auc)
            print(f"  [{name}] seed {seed}: AUC={auc:.4f}")
        out[name] = {
            "mean": float(np.mean(aucs)), "std": float(np.std(aucs)),
            "min": float(np.min(aucs)), "max": float(np.max(aucs)),
            "median": float(np.median(aucs)), "n_seeds": 5,
        }
    return out


def run_ensemble():
    """Transformer + 6 fixed features stacked via logistic regression."""
    legit_tr, byz_tr = gen_pbft_mm(N_TR)
    legit_te, byz_te = gen_pbft_mm(N_TE)
    # Train Transformer
    m = train_trf(legit_tr, byz_tr, epochs=50)
    m.eval()
    with torch.no_grad():
        trf_tr = m(torch.from_numpy(np.vstack([legit_tr, byz_tr]).astype(np.float32))).numpy().reshape(-1, 1)
        trf_te = m(torch.from_numpy(np.vstack([legit_te, byz_te]).astype(np.float32))).numpy().reshape(-1, 1)
    # Fixed features
    ff_tr = fixed_features(np.vstack([legit_tr, byz_tr]))
    ff_te = fixed_features(np.vstack([legit_te, byz_te]))
    y_tr = np.concatenate([np.zeros(len(legit_tr)), np.ones(len(byz_tr))])
    y_te = np.concatenate([np.zeros(len(legit_te)), np.ones(len(byz_te))])
    # Ensemble: Transformer logit + 6 fixed features -> 7 inputs to LR
    Xtr = np.hstack([trf_tr, ff_tr]); Xte = np.hstack([trf_te, ff_te])
    lr = LogisticRegression(C=1.0, max_iter=2000)
    lr.fit(Xtr, y_tr)
    auc_ens = roc_auc_score(y_te, lr.predict_proba(Xte)[:, 1])
    auc_trf = roc_auc_score(y_te, trf_te.ravel())
    return {"Ensemble_AUC": float(auc_ens), "Transformer_alone_AUC": float(auc_trf)}


def main():
    print("=== NE15 cross-protocol with bigger Transformer ===")
    xp = run_cross_protocol()
    for k, v in xp.items():
        print(f"  {k}: mean={v['mean']:.4f} median={v['median']:.4f} max={v['max']:.4f}")
    print("\n=== NE15 ensemble on PBFT MM ===")
    ens = run_ensemble()
    for k, v in ens.items():
        print(f"  {k}: {v:.4f}")

    results = {"cross_protocol": xp, "ensemble": ens}
    (OUT / "ne15.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    md = ["# NE15: Best-Result Push\n"]
    md.append("## Cross-protocol (bigger Transformer, 5 seeds)\n")
    md.append("| Protocol | mean | median | max | std |")
    md.append("|---|---:|---:|---:|---:|")
    for k, v in xp.items():
        md.append(f"| {k} | {v['mean']:.4f} | {v['median']:.4f} | {v['max']:.4f} | {v['std']:.4f} |")
    md.append("\n## Ensemble on PBFT MM\n")
    md.append("| Detector | AUC |")
    md.append("|---|---:|")
    for k, v in ens.items():
        md.append(f"| {k} | {v:.4f} |")
    (OUT / "REPORT.md").write_text("\n".join(md), encoding="utf-8")


if __name__ == "__main__":
    main()
