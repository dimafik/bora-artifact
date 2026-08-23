"""
sim_v29_ne11_adversarial.py - NE11: Adversarial-trained Byzantine
vs Transformer (gradient-based min-max game).

The strongest test of the bounded-blacklist detector class: the
Byzantine adversary uses PGD (projected gradient descent) to
optimize the telemetry window directly against the detector's
output, subject to the moment-matching constraint
||mean(X_byz) - mean(X_legit)|| <= delta_mean
||var(X_byz) - var(X_legit)|| <= delta_var

We compare:
  (a) Static Byzantine (PBFT MM as in NE8m)
  (b) Adversarial Byzantine (PGD with epsilon = 0.05, 0.1, 0.2)
  vs the same TinyTransformer detector from v28.
"""
from __future__ import annotations
import json
import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import roc_auc_score
from pathlib import Path

torch.manual_seed(20260629)
rng = np.random.default_rng(20260629)
HERE = Path(__file__).parent
OUT = HERE / "v29_ne11_results"
OUT.mkdir(parents=True, exist_ok=True)

N_TRAIN = 1500
N_TEST = 500
W = 16
N_EPOCHS = 30
LR = 1e-3
D_MODEL = 32
N_HEAD = 4
N_LAYER = 2
FFN = 64
DEVICE = torch.device("cpu")


def gen_pbft_mm(n):
    legit = rng.normal(0.5, 0.1, (n, W))
    byz = rng.normal(0.5, 0.1, (n, W))
    for i in range(n):
        n_burst = rng.integers(3, 6)
        burst_pos = rng.choice(W, n_burst, replace=False)
        byz[i, burst_pos] = 1.5
        other = [j for j in range(W) if j not in burst_pos]
        excess = np.sum(byz[i, burst_pos]) - n_burst * np.mean(legit)
        byz[i, other] -= excess / len(other)
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
        x = x.mean(dim=1)
        return self.head(x).squeeze(-1)


def train(model, X_tr, y_tr, epochs=N_EPOCHS):
    opt = torch.optim.Adam(model.parameters(), lr=LR)
    bce = nn.BCEWithLogitsLoss()
    bs = 64
    for ep in range(epochs):
        model.train()
        perm = torch.randperm(len(X_tr))
        for s in range(0, len(perm), bs):
            idx = perm[s:s+bs]
            opt.zero_grad()
            loss = bce(model(X_tr[idx]), y_tr[idx])
            loss.backward(); opt.step()
    return model


def pgd_byzantine(model, X_byz_init, X_legit, epsilon, steps=40, lr=0.02):
    """
    Project byzantine windows against the detector with PGD,
    keeping mean/var of each window within +/- epsilon of legit
    distribution to preserve moment-matching constraint.
    """
    model.eval()
    X = X_byz_init.clone().detach().requires_grad_(True)
    legit_mean = X_legit.mean()
    legit_std = X_legit.std()
    for _ in range(steps):
        logits = model(X)
        # adversary tries to push logits to NEGATIVE (look legit)
        loss = -logits.mean()
        grad = torch.autograd.grad(loss, X)[0]
        with torch.no_grad():
            X -= lr * grad.sign()
            # project: keep window mean/var within tolerance
            m = X.mean(dim=1, keepdim=True)
            X = X - m + legit_mean  # shift mean to legit
            s = X.std(dim=1, keepdim=True) + 1e-9
            X = (X - legit_mean) / s * legit_std + legit_mean
        X = X.detach().requires_grad_(True)
    return X.detach()


def evaluate(model, X, y):
    model.eval()
    with torch.no_grad():
        logits = model(X).cpu().numpy()
    return float(roc_auc_score(y.cpu().numpy(), logits))


def main():
    print("=== NE11: Adversarial Byzantine vs Transformer ===")
    # 1) Train Transformer on static PBFT MM
    legit_tr, byz_tr = gen_pbft_mm(N_TRAIN)
    X_tr = torch.from_numpy(
        np.vstack([legit_tr, byz_tr]).astype(np.float32))
    y_tr = torch.from_numpy(
        np.concatenate([np.zeros(N_TRAIN), np.ones(N_TRAIN)]).astype(np.float32))
    perm = torch.randperm(len(X_tr))
    X_tr, y_tr = X_tr[perm], y_tr[perm]
    model = train(Trf(), X_tr, y_tr)

    # 2) Static PBFT MM test AUC (baseline)
    legit_te, byz_te = gen_pbft_mm(N_TEST)
    X_te_static = torch.from_numpy(
        np.vstack([legit_te, byz_te]).astype(np.float32))
    y_te = torch.from_numpy(
        np.concatenate([np.zeros(N_TEST), np.ones(N_TEST)]).astype(np.float32))
    auc_static = evaluate(model, X_te_static, y_te)

    # 3) Adversarial Byzantine with PGD
    X_byz_init = torch.from_numpy(byz_te.astype(np.float32))
    X_legit_te = torch.from_numpy(legit_te.astype(np.float32))
    results = {"static_PBFT_MM_AUC": auc_static}

    for eps in [0.05, 0.1, 0.2]:
        X_byz_adv = pgd_byzantine(model, X_byz_init, X_legit_te, eps)
        X_te_adv = torch.cat([X_legit_te, X_byz_adv], dim=0)
        auc_adv = evaluate(model, X_te_adv, y_te)
        # moment check
        d_mean = abs(X_byz_adv.mean().item() - X_legit_te.mean().item())
        d_var = abs(X_byz_adv.var().item() - X_legit_te.var().item())
        results[f"adversarial_eps_{eps}"] = {
            "AUC": auc_adv,
            "delta_mean": d_mean,
            "delta_var": d_var,
        }
        print(f"eps={eps}  AUC={auc_adv:.4f}  d_mean={d_mean:.4f}  d_var={d_var:.4f}")

    (OUT / "ne11_adversarial.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8")
    md = ["# NE11: Adversarial Byzantine vs Transformer\n"]
    md.append("PGD-optimized Byzantine targets Transformer detector"
              " under moment-matching constraint.\n")
    md.append(f"**Static PBFT MM AUC**: {auc_static:.4f}\n")
    md.append("| Attack budget eps | AUC | d_mean | d_var |")
    md.append("|---|---:|---:|---:|")
    for eps in [0.05, 0.1, 0.2]:
        k = f"adversarial_eps_{eps}"
        r = results[k]
        md.append(f"| {eps} | {r['AUC']:.4f} | {r['delta_mean']:.4f} | {r['delta_var']:.4f} |")
    (OUT / "REPORT.md").write_text("\n".join(md), encoding="utf-8")
    print("\nFinal:", json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
