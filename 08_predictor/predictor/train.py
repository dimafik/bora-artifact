"""
train.py -- Train the multi-head Score Predictor on synthetic S-Raft traces.

Pre-registered protocol:
  - Adam, lr=3e-4, cosine schedule
  - Batch 128, 30 epochs
  - Loss weights (w_score, w_anom, w_degr) = (1.0, 0.3, 0.3) -- locked
  - Train/val/test split on seed buckets

KNOWN DEFECT IN THE SPLIT.  train() offsets the val and test seed buckets by
+1000 and +2000, and expand() then adds i*1000 for each of the four scenario
variants.  The two offsets are the same size, so the buckets intersect: with the
default 80/10/10 split, three of val's four scenario blocks and two of test's
four fall inside the training set.  Metrics this script prints for val and test
are therefore optimistic and should not be read as held-out performance.

No number in the paper depends on them.  The detection results are live testbed
measurements (02_results_raw/mldetect_*, x1_N*), and Table VI comes from
r11_necessity_baselines.py, which splits at seed offsets 0 and 10,000 -- far
enough apart that the scenario stride cannot bridge them.

The script is kept as it ran: the deployed checkpoint was trained by it, and
changing the split here would leave the shipped weights and the shipped code
describing different experiments.

Reports per-head metrics matching predictor_spec.md §6.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset, DataLoader

sys.path.insert(0, str(Path(__file__).parent))
from model import ScorePredictor, MultiTaskLoss, CONFIG  # noqa: E402


# =============================================================================
# Dataset
# =============================================================================


class WindowDataset(Dataset):
    def __init__(self, x: np.ndarray, df: pd.DataFrame):
        self.x = x.astype(np.float32)
        self.score = np.stack(
            [df["score_30s"], df["score_60s"], df["score_90s"]], axis=-1
        ).astype(np.float32)
        self.anom = df["byzantine"].to_numpy().astype(np.float32)
        self.deg = df["degrade"].to_numpy().astype(np.float32)

    def __len__(self) -> int:
        return len(self.x)

    def __getitem__(self, idx: int) -> dict:
        return {
            "x":       torch.from_numpy(self.x[idx]),
            "score":   torch.from_numpy(self.score[idx]),
            "anomaly": torch.tensor(self.anom[idx]),
            "degrade": torch.tensor(self.deg[idx]),
        }


def load_split(data_dir: Path, seeds: list[int]) -> tuple[np.ndarray, pd.DataFrame]:
    xs, dfs = [], []
    for f in sorted(data_dir.glob("*.parquet")):
        seed = int(f.stem.split("seed")[-1])
        if seed in seeds:
            xs_file = f.with_suffix(".npy")
            if not xs_file.exists():
                continue
            xs.append(np.load(xs_file))
            dfs.append(pd.read_parquet(f))
    if not dfs:
        empty_df = pd.DataFrame(columns=["score_30s", "score_60s", "score_90s", "byzantine", "degrade"])
        return np.zeros((0, 60, 8), dtype=np.float32), empty_df
    return np.concatenate(xs), pd.concat(dfs, ignore_index=True)


# =============================================================================
# Train loop
# =============================================================================


def evaluate(model: ScorePredictor, loader: DataLoader, device: str) -> dict:
    model.eval()
    score_preds, score_truth = [], []
    anom_preds, anom_truth = [], []
    deg_preds, deg_truth = [], []
    with torch.no_grad():
        for batch in loader:
            x = batch["x"].to(device)
            out = model(x)
            score_preds.append(out["score"][:, :, 1].cpu().numpy())  # median
            score_truth.append(batch["score"].numpy())
            anom_preds.append(out["anomaly"].squeeze(-1).cpu().numpy())
            anom_truth.append(batch["anomaly"].numpy())
            deg_preds.append(out["degrade"].squeeze(-1).cpu().numpy())
            deg_truth.append(batch["degrade"].numpy())

    score_p = np.concatenate(score_preds)
    score_t = np.concatenate(score_truth)
    anom_p = np.concatenate(anom_preds)
    anom_t = np.concatenate(anom_truth)
    deg_p = np.concatenate(deg_preds)
    deg_t = np.concatenate(deg_truth)

    # Score RMSE per horizon
    score_rmse = np.sqrt(((score_p - score_t) ** 2).mean(axis=0)).tolist()

    # Anomaly AUC-ROC (manual, no sklearn dependency)
    def auc_roc(y_true, y_pred):
        order = np.argsort(-y_pred)
        y = y_true[order]
        n_pos = y.sum()
        n_neg = len(y) - n_pos
        if n_pos == 0 or n_neg == 0:
            return float("nan")
        tp = np.cumsum(y)
        fp = np.cumsum(1 - y)
        tpr = tp / n_pos
        fpr = fp / n_neg
        return float(np.trapz(tpr, fpr))

    return {
        "score_rmse_30s": score_rmse[0],
        "score_rmse_60s": score_rmse[1],
        "score_rmse_90s": score_rmse[2],
        "anom_auc":       auc_roc(anom_t, anom_p),
        "anom_pos_rate":  float(anom_t.mean()),
        "degrade_auc":    auc_roc(deg_t, deg_p),
        "degrade_pos_rate": float(deg_t.mean()),
    }


def train(args) -> int:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")

    train_seeds = list(range(args.seed_offset, args.seed_offset + args.n_train))
    val_seeds = list(range(args.seed_offset + 1000, args.seed_offset + 1000 + args.n_val))
    test_seeds = list(range(args.seed_offset + 2000, args.seed_offset + 2000 + args.n_test))

    # Expand each seed bucket to its 4 scenario variants
    def expand(seeds):
        out = []
        for s in seeds:
            for i in range(4):  # 4 scenarios
                out.append(s + i * 1000)
        return out
    train_x, train_df = load_split(args.data_dir, expand(train_seeds))
    val_x, val_df = load_split(args.data_dir, expand(val_seeds))
    test_x, test_df = load_split(args.data_dir, expand(test_seeds))

    print(f"Train: {len(train_df):,} windows, "
          f"Val: {len(val_df):,}, Test: {len(test_df):,}")
    if len(train_df) == 0:
        print("ERROR: no training data found.")
        return 1

    train_loader = DataLoader(WindowDataset(train_x, train_df), batch_size=128, shuffle=True, num_workers=0)
    val_loader = DataLoader(WindowDataset(val_x, val_df), batch_size=256, num_workers=0)
    test_loader = DataLoader(WindowDataset(test_x, test_df), batch_size=256, num_workers=0)

    model = ScorePredictor().to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=3e-4, weight_decay=1e-5)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=args.epochs)
    criterion = MultiTaskLoss()

    best_val = float("inf")
    history = []

    for epoch in range(args.epochs):
        model.train()
        train_losses = {"loss": 0.0, "l_score": 0.0, "l_anom": 0.0, "l_degr": 0.0}
        n_batches = 0
        for batch in train_loader:
            x = batch["x"].to(device)
            target = {
                "score":   batch["score"].to(device),
                "anomaly": batch["anomaly"].to(device),
                "degrade": batch["degrade"].to(device),
            }
            pred = model(x)
            losses = criterion(pred, target)
            optimizer.zero_grad()
            losses["loss"].backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            for k in train_losses:
                train_losses[k] += float(losses[k].item())
            n_batches += 1
        scheduler.step()

        for k in train_losses:
            train_losses[k] /= max(n_batches, 1)

        val_metrics = evaluate(model, val_loader, device)
        history.append({"epoch": epoch, **train_losses, **val_metrics})

        line = (f"E{epoch:02d} loss={train_losses['loss']:.4f} "
                f"val_score_rmse@30={val_metrics['score_rmse_30s']:.4f} "
                f"val_anom_auc={val_metrics['anom_auc']:.3f} "
                f"val_deg_auc={val_metrics['degrade_auc']:.3f}")
        print(line)

        if val_metrics["score_rmse_30s"] < best_val:
            best_val = val_metrics["score_rmse_30s"]
            args.out_dir.mkdir(parents=True, exist_ok=True)
            torch.save({
                "model_state_dict": model.state_dict(),
                "config":           CONFIG.__dict__,
                "epoch":            epoch,
                "val_metrics":      val_metrics,
            }, args.out_dir / "best.pt")

    # Final test eval with best checkpoint
    ckpt = torch.load(args.out_dir / "best.pt", map_location=device)
    model.load_state_dict(ckpt["model_state_dict"])
    test_metrics = evaluate(model, test_loader, device)

    print(f"\n--- TEST (using epoch {ckpt['epoch']} checkpoint) ---")
    for k, v in test_metrics.items():
        print(f"  {k}: {v:.4f}" if isinstance(v, float) else f"  {k}: {v}")

    # Save history + final
    (args.out_dir / "history.json").write_text(json.dumps(history, indent=2))
    (args.out_dir / "test_metrics.json").write_text(json.dumps(test_metrics, indent=2))

    # Acceptance check vs pre-registered thresholds
    acceptance = {
        "score_rmse_30s_passes":  test_metrics["score_rmse_30s"] <= 0.04,
        "anom_auc_passes":        test_metrics["anom_auc"] >= 0.90 if not np.isnan(test_metrics["anom_auc"]) else False,
        "degrade_auc_passes":     test_metrics["degrade_auc"] >= 0.70 if not np.isnan(test_metrics["degrade_auc"]) else False,
    }
    print(f"\nAcceptance (pre-registered):")
    for k, v in acceptance.items():
        print(f"  {k}: {v}")

    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--epochs", type=int, default=30)
    ap.add_argument("--seed-offset", type=int, default=0)
    ap.add_argument("--n-train", type=int, default=80)
    ap.add_argument("--n-val", type=int, default=10)
    ap.add_argument("--n-test", type=int, default=10)
    args = ap.parse_args()
    return train(args)


if __name__ == "__main__":
    raise SystemExit(main())
