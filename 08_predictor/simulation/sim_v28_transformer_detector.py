"""
sim_v28_transformer_detector.py - NE8m++ Transformer adaptive
detector on PBFT MM hard regime.

v23 NE8m+ probed fixed higher-order features (kurtosis, AR(1),
range/IQR) on PBFT MM and found only modest improvement
(direction-invariant AUC <= 0.574). The deferred work was
"adaptive Transformer-class detector".

v28 implements a small encoder-only Transformer:
  Input: window of W=16 ticks, 1 channel (CC telemetry)
  Architecture: 2-layer encoder, d_model=32, n_head=4, FFN=64
  Output: binary class (legit vs Byzantine MM)
  Train: 1500 each, 30 epochs, Adam
  Test: hold-out 500 each
"""
from __future__ import annotations
import json
import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import roc_auc_score
from pathlib import Path

torch.manual_seed(20260628)
rng = np.random.default_rng(20260628)
HERE = Path(__file__).parent
OUT = HERE / "v28_transformer_results"
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
        target_var = np.var(legit[i])
        cur_var = np.var(byz[i])
        if cur_var > 0:
            byz[i] = ((byz[i] - np.mean(byz[i])) *
                      np.sqrt(target_var / cur_var) + np.mean(byz[i]))
    return legit, byz


def make_dataset(n):
    legit, byz = gen_pbft_mm(n)
    X = np.vstack([legit, byz]).astype(np.float32)
    y = np.concatenate([np.zeros(n), np.ones(n)]).astype(np.float32)
    perm = rng.permutation(len(y))
    return X[perm], y[perm]


class PositionalEncoding(nn.Module):
    def __init__(self, d, max_len=64):
        super().__init__()
        pe = torch.zeros(max_len, d)
        pos = torch.arange(max_len).unsqueeze(1).float()
        div = torch.exp(torch.arange(0, d, 2).float() *
                        (-np.log(10000.0) / d))
        pe[:, 0::2] = torch.sin(pos * div)
        pe[:, 1::2] = torch.cos(pos * div)
        self.register_buffer("pe", pe)

    def forward(self, x):
        return x + self.pe[: x.size(1)]


class TinyTransformer(nn.Module):
    def __init__(self):
        super().__init__()
        self.proj = nn.Linear(1, D_MODEL)
        self.pe = PositionalEncoding(D_MODEL)
        layer = nn.TransformerEncoderLayer(
            d_model=D_MODEL, nhead=N_HEAD, dim_feedforward=FFN,
            batch_first=True, dropout=0.1
        )
        self.enc = nn.TransformerEncoder(layer, N_LAYER)
        self.head = nn.Linear(D_MODEL, 1)

    def forward(self, x):
        # x: (B, W)
        x = x.unsqueeze(-1)  # (B, W, 1)
        x = self.proj(x)
        x = self.pe(x)
        x = self.enc(x)
        x = x.mean(dim=1)
        return self.head(x).squeeze(-1)


def train_and_eval():
    X_tr, y_tr = make_dataset(N_TRAIN)
    X_te, y_te = make_dataset(N_TEST)

    model = TinyTransformer().to(DEVICE)
    opt = torch.optim.Adam(model.parameters(), lr=LR)
    bce = nn.BCEWithLogitsLoss()
    n_params = sum(p.numel() for p in model.parameters())
    print(f"params: {n_params}")

    X_tr_t = torch.from_numpy(X_tr).to(DEVICE)
    y_tr_t = torch.from_numpy(y_tr).to(DEVICE)
    X_te_t = torch.from_numpy(X_te).to(DEVICE)
    y_te_t = torch.from_numpy(y_te).to(DEVICE)

    bs = 64
    for epoch in range(N_EPOCHS):
        model.train()
        perm = torch.randperm(len(X_tr_t))
        ep_loss = 0.0
        for s in range(0, len(perm), bs):
            idx = perm[s:s+bs]
            opt.zero_grad()
            logits = model(X_tr_t[idx])
            loss = bce(logits, y_tr_t[idx])
            loss.backward()
            opt.step()
            ep_loss += loss.item() * len(idx)
        ep_loss /= len(perm)
        if (epoch + 1) % 5 == 0 or epoch == 0:
            model.eval()
            with torch.no_grad():
                te_logits = model(X_te_t).cpu().numpy()
            auc = roc_auc_score(y_te, te_logits)
            print(f"epoch {epoch+1:2d}  loss={ep_loss:.4f}  test AUC={auc:.4f}")

    model.eval()
    with torch.no_grad():
        te_logits = model(X_te_t).cpu().numpy()
    auc = roc_auc_score(y_te, te_logits)
    return auc, n_params


def main():
    print(f"PyTorch {torch.__version__} | device {DEVICE}")
    auc, n_params = train_and_eval()
    print(f"\n=== Final Transformer AUC on PBFT MM hard regime: {auc:.4f} ===")

    # Comparison with v23 baselines
    baselines = {
        "Linear (v23)": 0.4911,
        "AR(1) memory (v23)": 0.5461,
        "Kurtosis (v23)": 0.5743,  # direction-invariant
        "Range/IQR (v23)": 0.5300,
        "Combined higher-order (v23)": 0.5020,
        "TinyTransformer (v28)": auc,
    }

    result = {
        "experiment": "NE8m++ Transformer adaptive detector on PBFT MM",
        "model": "encoder-only Transformer (d=32, nhead=4, layers=2)",
        "n_parameters": int(n_params),
        "n_train": N_TRAIN * 2,
        "n_test": N_TEST * 2,
        "window_W": W,
        "epochs": N_EPOCHS,
        "test_AUC_transformer": float(auc),
        "comparison_with_v23_features": baselines,
        "improvement_over_best_v23_fixed_feature": float(auc - 0.5743),
    }
    (OUT / "ne8m_plus_plus.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8")
    md = ["# NE8m++ Adaptive Transformer Detector on PBFT MM\n"]
    md.append("Closes v23 deferred work on PBFT MM hard regime.\n")
    md.append("| Detector | AUC |")
    md.append("|---|---:|")
    for k, v in baselines.items():
        emph = "**" if "Transformer" in k else ""
        md.append(f"| {emph}{k}{emph} | {emph}{v:.4f}{emph} |")
    md.append("")
    md.append(f"**TinyTransformer params**: {n_params}")
    md.append(f"**Improvement over best fixed feature (v23)**: "
              f"{auc - 0.5743:+.4f}")
    (OUT / "REPORT.md").write_text("\n".join(md), encoding="utf-8")


if __name__ == "__main__":
    main()
