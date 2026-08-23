"""
train_v3_balanced.py -- Class-balanced training for the degrade head.

Strategy:
  - Weighted BCE for degrade head (positive weight = N_neg / N_pos)
  - Increase degrade head loss weight 0.3 → 1.0 (rebalance from score-dominant)
  - Same data (data_xl2) and architecture, just rebalance training signal

Goal: lift Degrade test precision@10% past 0.70 pre-registered threshold.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch.utils.data import DataLoader

sys.path.insert(0, str(Path(__file__).parent))
from model import ScorePredictor, CONFIG  # noqa: E402
from train import WindowDataset, load_split  # noqa: E402


def pinball_loss(y_pred, y_true, quantiles):
    diffs = y_true.unsqueeze(-1) - y_pred
    q = torch.tensor(quantiles, device=y_pred.device).view(1, 1, -1)
    return torch.mean(torch.max(q * diffs, (q - 1) * diffs))


def auc_roc(y_true, y_pred):
    order = np.argsort(-y_pred)
    y = y_true[order]
    n_pos = y.sum()
    n_neg = len(y) - n_pos
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    tp = np.cumsum(y)
    fp = np.cumsum(1 - y)
    return float(np.trapz(tp / n_pos, fp / n_neg))


def evaluate(model, loader, device):
    model.eval()
    score_p, score_t, anom_p, anom_t, deg_p, deg_t = [], [], [], [], [], []
    with torch.no_grad():
        for batch in loader:
            x = batch["x"].to(device)
            out = model(x)
            score_p.append(out["score"][:, :, 1].cpu().numpy())
            score_t.append(batch["score"].numpy())
            anom_p.append(out["anomaly"].squeeze(-1).cpu().numpy())
            anom_t.append(batch["anomaly"].numpy())
            deg_p.append(out["degrade"].squeeze(-1).cpu().numpy())
            deg_t.append(batch["degrade"].numpy())

    score_p = np.concatenate(score_p)
    score_t = np.concatenate(score_t)
    anom_p = np.concatenate(anom_p)
    anom_t = np.concatenate(anom_t)
    deg_p = np.concatenate(deg_p)
    deg_t = np.concatenate(deg_t)

    rmse = np.sqrt(((score_p - score_t) ** 2).mean(axis=0)).tolist()
    k = max(1, len(deg_p) // 10)
    top_k_idx = np.argsort(-deg_p)[:k]
    deg_p10 = float(deg_t[top_k_idx].mean()) if k > 0 else float("nan")

    return {
        "score_rmse_30s": rmse[0],
        "score_rmse_60s": rmse[1],
        "score_rmse_90s": rmse[2],
        "anom_auc":       auc_roc(anom_t, anom_p),
        "degrade_auc":    auc_roc(deg_t, deg_p),
        "degrade_p10":    deg_p10,
        "degrade_pos_rate": float(deg_t.mean()),
    }


def train(args):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")

    def expand(seeds):
        return [s + i * 1000 for s in seeds for i in range(4)]

    train_seeds = list(range(args.seed_offset, args.seed_offset + args.n_train))
    val_seeds = list(range(args.seed_offset + 100, args.seed_offset + 100 + args.n_val))

    train_x, train_df = load_split(args.data_dir, expand(train_seeds))
    val_x, val_df = load_split(args.data_dir, expand(val_seeds))

    print(f"Train: {len(train_df):,} windows, Val: {len(val_df):,}")
    print(f"  train degrade pos rate: {train_df['degrade'].mean():.4f}")
    print(f"  val   degrade pos rate: {val_df['degrade'].mean():.4f}")
    if len(train_df) == 0:
        return 1

    # Class-balanced sampler for training
    deg = train_df["degrade"].to_numpy()
    n_pos = int(deg.sum())
    n_neg = len(deg) - n_pos
    pos_weight = (n_neg / max(n_pos, 1))
    print(f"  positive weight for degrade BCE: {pos_weight:.2f}")

    train_loader = DataLoader(
        WindowDataset(train_x, train_df), batch_size=128, shuffle=True
    )
    val_loader = DataLoader(WindowDataset(val_x, val_df), batch_size=256)

    model = ScorePredictor().to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=3e-4, weight_decay=1e-5)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)

    pos_weight_tensor = torch.tensor([pos_weight], device=device)
    bce_anom = torch.nn.BCELoss()
    bce_deg_weighted = torch.nn.BCEWithLogitsLoss(pos_weight=pos_weight_tensor)
    # We use BCEWithLogits, so we need to bypass the sigmoid in the head.
    # Workaround: convert sigmoid output back via logit, or modify model.
    # Simpler: use BCELoss with manual pos-weighted reweighting.

    def bce_pos_weighted(pred, target, w_pos):
        eps = 1e-7
        pred_clamped = pred.clamp(eps, 1 - eps)
        loss = -(w_pos * target * torch.log(pred_clamped)
                 + (1 - target) * torch.log(1 - pred_clamped))
        return loss.mean()

    # Loss weights: emphasize degrade head
    W_SCORE, W_ANOM, W_DEGR = 1.0, 0.3, 2.0   # was 1.0/0.3/0.3
    best_p10 = -1.0
    args.out_dir.mkdir(parents=True, exist_ok=True)
    history = []

    for epoch in range(args.epochs):
        model.train()
        running = {"loss": 0, "ls": 0, "la": 0, "ld": 0}
        nb = 0
        for batch in train_loader:
            x = batch["x"].to(device)
            target_s = batch["score"].to(device)
            target_a = batch["anomaly"].to(device)
            target_d = batch["degrade"].to(device)
            pred = model(x)
            l_s = pinball_loss(pred["score"], target_s, CONFIG.quantiles)
            l_a = bce_anom(pred["anomaly"].squeeze(-1), target_a)
            l_d = bce_pos_weighted(
                pred["degrade"].squeeze(-1), target_d, pos_weight
            )
            loss = W_SCORE * l_s + W_ANOM * l_a + W_DEGR * l_d
            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            running["loss"] += float(loss.item())
            running["ls"] += float(l_s.item())
            running["la"] += float(l_a.item())
            running["ld"] += float(l_d.item())
            nb += 1
        scheduler.step()

        for k in running:
            running[k] /= max(nb, 1)

        val = evaluate(model, val_loader, device)
        history.append({"epoch": epoch, **running, **val})

        print(f"E{epoch:02d} loss={running['loss']:.4f} "
              f"ls={running['ls']:.4f} la={running['la']:.4f} ld={running['ld']:.4f} "
              f"| val_rmse@30={val['score_rmse_30s']:.4f} "
              f"val_deg_auc={val['degrade_auc']:.4f} "
              f"val_deg_p10={val['degrade_p10']:.4f}")

        if val["degrade_p10"] > best_p10:
            best_p10 = val["degrade_p10"]
            torch.save({
                "model_state_dict": model.state_dict(),
                "epoch": epoch,
                "val_metrics": val,
                "config": CONFIG.__dict__,
            }, args.out_dir / "best.pt")

    (args.out_dir / "history.json").write_text(json.dumps(history, indent=2))
    print(f"\nBest val degrade_p10: {best_p10:.4f}")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--epochs", type=int, default=10)
    ap.add_argument("--seed-offset", type=int, default=0)
    ap.add_argument("--n-train", type=int, default=10)
    ap.add_argument("--n-val", type=int, default=2)
    return train(ap.parse_args())


if __name__ == "__main__":
    raise SystemExit(main())
