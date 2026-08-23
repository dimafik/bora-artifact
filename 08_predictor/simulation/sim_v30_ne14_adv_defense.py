"""
sim_v30_ne14_adv_defense.py - NE14: Adversarially-trained
Transformer defense (push NE11 0.821 -> higher).

Adversarial training: every epoch, generate PGD-attacked Byzantine
samples and add to training set. The Transformer learns to be
robust to gradient-based attackers.
"""
from __future__ import annotations
import json
import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import roc_auc_score
from pathlib import Path

torch.manual_seed(20260701)
rng = np.random.default_rng(20260701)
HERE = Path(__file__).parent
OUT = HERE / "v30_ne14_results"
OUT.mkdir(parents=True, exist_ok=True)

N_TR, N_TE, W = 1500, 500, 16
N_EPOCH = 40
LR = 1e-3
D_MODEL = 48
N_HEAD = 6
N_LAYER = 3
FFN = 96


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
            byz[i] = ((byz[i] - np.mean(byz[i])) * np.sqrt(tv / cv) + np.mean(byz[i]))
    return legit, byz


class PE(nn.Module):
    def __init__(self, d, m=64):
        super().__init__()
        pe = torch.zeros(m, d)
        pos = torch.arange(m).unsqueeze(1).float()
        div = torch.exp(torch.arange(0, d, 2).float() * (-np.log(10000.0) / d))
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
            batch_first=True, dropout=0.15)
        self.enc = nn.TransformerEncoder(layer, N_LAYER)
        self.head = nn.Sequential(nn.Linear(D_MODEL, 32), nn.GELU(), nn.Linear(32, 1))
    def forward(self, x):
        x = x.unsqueeze(-1)
        x = self.proj(x); x = self.pe(x); x = self.enc(x)
        return self.head(x.mean(dim=1)).squeeze(-1)


def pgd(model, X, X_legit, eps=0.1, steps=20, lr=0.02):
    """Generate PGD-attacked byzantine windows."""
    model.eval()
    X = X.clone().detach().requires_grad_(True)
    lm, ls = X_legit.mean(), X_legit.std()
    for _ in range(steps):
        logits = model(X)
        loss = -logits.mean()
        g = torch.autograd.grad(loss, X)[0]
        with torch.no_grad():
            X -= lr * g.sign()
            X = X - X.mean(dim=1, keepdim=True) + lm
            s = X.std(dim=1, keepdim=True) + 1e-9
            X = (X - lm) / s * ls + lm
        X = X.detach().requires_grad_(True)
    return X.detach()


def adversarial_train():
    legit_tr, byz_tr = gen_pbft_mm(N_TR)
    X_l = torch.from_numpy(legit_tr.astype(np.float32))
    X_b = torch.from_numpy(byz_tr.astype(np.float32))
    model = Trf()
    opt = torch.optim.Adam(model.parameters(), lr=LR, weight_decay=1e-5)
    sch = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=N_EPOCH)
    bce = nn.BCEWithLogitsLoss()
    bs = 64
    n_params = sum(p.numel() for p in model.parameters())
    print(f"params: {n_params}")
    for ep in range(N_EPOCH):
        # generate adversarial byzantine batch (50% mix)
        if ep >= 5:
            X_b_adv = pgd(model, X_b[:N_TR//2], X_l, eps=0.1, steps=10)
            X_combined = torch.cat([X_l, X_b[:N_TR//2], X_b_adv], dim=0)
            y_combined = torch.cat([
                torch.zeros(len(X_l)),
                torch.ones(N_TR//2),
                torch.ones(N_TR//2)], dim=0)
        else:
            X_combined = torch.cat([X_l, X_b], dim=0)
            y_combined = torch.cat([torch.zeros(len(X_l)), torch.ones(len(X_b))], dim=0)
        perm = torch.randperm(len(X_combined))
        X_combined, y_combined = X_combined[perm], y_combined[perm]
        model.train()
        ep_loss = 0
        for s in range(0, len(perm), bs):
            idx = slice(s, s+bs)
            opt.zero_grad()
            loss = bce(model(X_combined[idx]), y_combined[idx])
            loss.backward(); opt.step()
            ep_loss += loss.item()
        sch.step()
        if (ep + 1) % 10 == 0:
            print(f"  ep {ep+1}/{N_EPOCH}  loss={ep_loss/(len(perm)/bs):.4f}")
    return model, n_params


def evaluate(model, X, y):
    model.eval()
    with torch.no_grad():
        return float(roc_auc_score(y.numpy(), model(X).numpy()))


def main():
    print("=== NE14: Adversarial-Trained Transformer Defense ===")
    model, n_params = adversarial_train()
    legit_te, byz_te = gen_pbft_mm(N_TE)
    X_l_te = torch.from_numpy(legit_te.astype(np.float32))
    X_b_te = torch.from_numpy(byz_te.astype(np.float32))
    y_te = torch.cat([torch.zeros(N_TE), torch.ones(N_TE)])
    # static baseline
    auc_static = evaluate(model, torch.cat([X_l_te, X_b_te]), y_te)
    print(f"Static PBFT MM (defended): {auc_static:.4f}")
    # PGD-attacked at multiple budgets
    results = {"n_params": n_params, "static_AUC_defended": auc_static, "adversarial": {}}
    for eps in [0.05, 0.1, 0.2, 0.3]:
        X_b_adv = pgd(model, X_b_te, X_l_te, eps=eps, steps=30)
        auc_adv = evaluate(model, torch.cat([X_l_te, X_b_adv]), y_te)
        results["adversarial"][f"eps_{eps}"] = auc_adv
        print(f"PGD eps={eps}: AUC={auc_adv:.4f}")
    (OUT / "ne14.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    md = ["# NE14: Adversarial-Trained Transformer Defense\n"]
    md.append(f"params: {n_params}\n")
    md.append(f"Static (defended): AUC = {auc_static:.4f}\n")
    md.append("| PGD eps | AUC |")
    md.append("|---|---:|")
    for eps in [0.05, 0.1, 0.2, 0.3]:
        md.append(f"| {eps} | {results['adversarial'][f'eps_{eps}']:.4f} |")
    md.append("\n**Comparison vs v29 NE11**: NE11 undefended AUC=0.821 under PGD; NE14 defended AUC reported above.")
    (OUT / "REPORT.md").write_text("\n".join(md), encoding="utf-8")


if __name__ == "__main__":
    main()
