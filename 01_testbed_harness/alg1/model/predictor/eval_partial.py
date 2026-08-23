"""
eval_partial.py -- Evaluate current best.pt on a fresh held-out test set.
Reports the metrics required for the v26 manuscript results tables:
  - Score RMSE @30s, 60s, 90s
  - Anomaly AUC
  - Degradation AUC, precision@10%, recall

Re-evaluates AGAINST a fresh test split disjoint from training seeds.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

sys.path.insert(0, str(Path(__file__).parent))
from model import ScorePredictor, CONFIG  # noqa: E402


DATA_DIR = Path(__file__).parent.parent / "data_xl2"
CHECKPOINT = Path(__file__).parent.parent / "model_xl2" / "best.pt"


def load_test_split(seeds: list[int]):
    xs, dfs = [], []
    for f in sorted(DATA_DIR.glob("*.parquet")):
        seed = int(f.stem.split("seed")[-1])
        if seed in seeds:
            xs_file = f.with_suffix(".npy")
            if not xs_file.exists():
                continue
            xs.append(np.load(xs_file))
            dfs.append(pd.read_parquet(f))
    if not dfs:
        return None, None
    return np.concatenate(xs), pd.concat(dfs, ignore_index=True)


def auc_roc(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    order = np.argsort(-y_pred)
    y = y_true[order]
    n_pos = y.sum()
    n_neg = len(y) - n_pos
    if n_pos == 0 or n_neg == 0:
        return float("nan")
    tp = np.cumsum(y)
    fp = np.cumsum(1 - y)
    return float(np.trapz(tp / n_pos, fp / n_neg))


def wilson_ci(s: int, n: int, conf=0.99):
    import math
    from scipy import stats as st
    if n == 0:
        return (0.0, 1.0)
    z = st.norm.ppf((1 + conf) / 2)
    p_hat = s / n
    denom = 1 + z**2 / n
    center = (p_hat + z**2 / (2 * n)) / denom
    half = z * math.sqrt(p_hat * (1 - p_hat) / n + z**2 / (4 * n**2)) / denom
    return (max(0.0, center - half), min(1.0, center + half))


def main():
    # Balanced test split: last 20% from EACH scenario, not by raw seed sort.
    # Otherwise all "degrade" traces fall in the test set (high seed numbers).
    by_scenario = {}
    for f in sorted(DATA_DIR.glob("*.parquet")):
        scenario = f.stem.split("_seed")[0]
        seed = int(f.stem.split("seed")[-1])
        by_scenario.setdefault(scenario, []).append(seed)

    test_seeds = []
    for scenario, seeds in by_scenario.items():
        sorted_seeds = sorted(seeds)
        k = max(1, len(sorted_seeds) // 5)
        test_seeds.extend(sorted_seeds[-k:])

    n_total = sum(len(v) for v in by_scenario.values())
    print(f"Test seeds: {len(test_seeds)} of {n_total} files (balanced across scenarios)")
    x, df = load_test_split(test_seeds)
    print(f"Test windows: {len(df):,}")

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Device: {device}")

    ckpt = torch.load(CHECKPOINT, map_location=device)
    model = ScorePredictor().to(device)
    model.load_state_dict(ckpt["model_state_dict"])
    model.eval()
    print(f"Loaded checkpoint from epoch {ckpt['epoch']}, val metrics: "
          f"{ckpt.get('val_metrics', {})}")

    # Predict in batches
    batch_size = 512
    score_preds, anom_preds, deg_preds = [], [], []
    with torch.no_grad():
        for i in range(0, len(x), batch_size):
            xb = torch.from_numpy(x[i:i+batch_size]).to(device)
            out = model(xb)
            score_preds.append(out["score"][:, :, 1].cpu().numpy())  # median quantile
            anom_preds.append(out["anomaly"].squeeze(-1).cpu().numpy())
            deg_preds.append(out["degrade"].squeeze(-1).cpu().numpy())

    score_p = np.concatenate(score_preds)  # (N, 3 horizons)
    anom_p = np.concatenate(anom_preds)
    deg_p = np.concatenate(deg_preds)

    score_t = np.stack(
        [df["score_30s"], df["score_60s"], df["score_90s"]], axis=-1
    ).astype(np.float32)
    anom_t = df["byzantine"].to_numpy().astype(int)
    deg_t = df["degrade"].to_numpy().astype(int)

    # Score RMSE per horizon
    rmse = np.sqrt(((score_p - score_t) ** 2).mean(axis=0)).tolist()

    # AUCs
    anom_auc = auc_roc(anom_t, anom_p)
    deg_auc = auc_roc(deg_t, deg_p)

    # Top-10% precision for degrade
    k = max(1, len(deg_p) // 10)
    top_k_idx = np.argsort(-deg_p)[:k]
    deg_top_correct = int(deg_t[top_k_idx].sum())
    deg_top_precision = deg_top_correct / k
    deg_recall = deg_top_correct / max(deg_t.sum(), 1)
    deg_p10_ci = wilson_ci(deg_top_correct, k)

    print()
    print("=== HELD-OUT TEST RESULTS ===")
    print(f"  n test windows : {len(df):,}")
    print(f"  positive rate anom : {anom_t.mean():.4f}")
    print(f"  positive rate degr : {deg_t.mean():.4f}")
    print()
    print(f"  Score RMSE @30s : {rmse[0]:.4f}")
    print(f"  Score RMSE @60s : {rmse[1]:.4f}")
    print(f"  Score RMSE @90s : {rmse[2]:.4f}")
    print(f"  Anomaly AUC     : {anom_auc:.4f}")
    print(f"  Degrade AUC     : {deg_auc:.4f}")
    print(f"  Degrade precision@10%: {deg_top_precision:.4f} "
          f"(99% Wilson CI [{deg_p10_ci[0]:.3f}, {deg_p10_ci[1]:.3f}])")
    print(f"  Degrade recall  : {deg_recall:.4f}")
    print()

    pre_reg = {
        "Score RMSE @30s <= 0.04":  rmse[0] <= 0.04,
        "Anomaly AUC >= 0.90":      anom_auc >= 0.90,
        "Degrade prec@10% >= 0.70": deg_top_precision >= 0.70,
    }
    print("=== PRE-REGISTERED ACCEPTANCE ===")
    for k, v in pre_reg.items():
        print(f"  {k}: {'PASS' if v else 'FAIL'}")

    # Save JSON
    import json
    out_json = Path(__file__).parent.parent / "model_full" / "eval_partial_results.json"
    out_json.write_text(json.dumps({
        "n_test": len(df),
        "score_rmse_30s": rmse[0],
        "score_rmse_60s": rmse[1],
        "score_rmse_90s": rmse[2],
        "anomaly_auc": anom_auc,
        "degrade_auc": deg_auc,
        "degrade_precision_at_10pct": deg_top_precision,
        "degrade_precision_at_10pct_ci99": list(deg_p10_ci),
        "degrade_recall": deg_recall,
        "n_train_epochs_used": ckpt["epoch"],
    }, indent=2))
    print(f"\nResults saved to {out_json}")


if __name__ == "__main__":
    main()
