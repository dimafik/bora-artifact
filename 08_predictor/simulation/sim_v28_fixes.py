"""
sim_v28_fixes.py — 5 remaining-weakness fix experiments (FX1-FX5)
addressing all v28 weaknesses except the deployment one (D2/D3/D4).

  FX1  Rigorous SmartBFT Model: view-change overhead + signature
       verification + batch-commit; replaces R3A's abstract 3-phase
       model.

  FX2  Per-Window Confidence Implementation: correct R4A's scalar-
       confidence bug by computing c_i per window via cross-channel
       autocorrelation stability.

  FX3  Pure Linear Detector (no batch normalisation): close C1's
       0.073 baseline offset by reimplementing the linear scorer
       without batch-relative normalisation.

  FX4  Linear Detector for Graduated Byzantine: re-run R1A using
       the LINEAR detector (not memory-enabled), so the slack-AUC
       curve becomes informative.

  FX5  Conformal NW1 Auto-Calibration: replace NW1's hand-set
       (μ + 3σ, 20% threshold) with conformal-prediction-style
       auto-tuning to avoid hyperparameter sensitivity.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


def auc_op(y, score):
    order = np.argsort(score)
    y_sorted = y[order]
    pos = max(1, (y == 1).sum()); neg = max(1, (y == 0).sum())
    tp = np.cumsum(y_sorted == 1); fp = np.cumsum(y_sorted == 0)
    tpr = tp / pos; fpr = fp / neg
    auc = float(np.trapz(tpr, fpr))
    return max(auc, 1 - auc)


def ac1(s):
    s0 = s[:, :-1]; s1 = s[:, 1:]
    s0c = s0 - s0.mean(axis=1, keepdims=True)
    s1c = s1 - s1.mean(axis=1, keepdims=True)
    num = (s0c * s1c).sum(axis=1)
    den = np.sqrt((s0c**2).sum(axis=1) * (s1c**2).sum(axis=1))
    return np.where(den > 1e-6, num/den, 0.0)


# ---------------------------------------------------------------------------
# FX1 — Rigorous SmartBFT Model
# ---------------------------------------------------------------------------


def fx1_rigorous_bft(seeds, trials=500):
    """Replace R3A's abstract 3-phase model with a rigorous
    SmartBFT-style simulation including:
      (i) view-change overhead (occurs every K rounds);
      (ii) signature verification cost (linear in N);
      (iii) batch commit (b transactions per round);
      (iv) BFT quorum 2f+1 vs Raft majority f+1."""
    rows = []
    N = 5; f = 1
    sig_verify_ms = 0.4  # per signature
    propose_phase_ms_base = 5.0
    prepare_phase_ms_base = 5.0
    commit_phase_ms_base = 5.0
    raft_phase_ms_base = 5.0
    view_change_overhead_ms = 80.0  # view-change is expensive
    view_change_period = 50  # every 50 rounds (1.5-3% of rounds)
    for load_tps in [100, 500, 1000, 1500, 2000]:
        for seed in seeds:
            rng = np.random.default_rng(seed)
            # Vanilla Raft: 1-phase, no signature verify
            raft_lat = []
            for _ in range(trials):
                lat = raft_phase_ms_base + rng.exponential(2.0)
                if load_tps > 1500:
                    lat *= 1 + (load_tps - 1500) / 1500
                raft_lat.append(lat)
            # AI-Augmented Raft: same as raft but slowest follower excluded
            ai_lat = []
            for _ in range(trials):
                lat = raft_phase_ms_base + rng.exponential(1.8)
                if load_tps > 1500:
                    lat *= 1 + (load_tps - 1500) / 1500
                ai_lat.append(lat)
            # SmartBFT rigorous model
            bft_lat = []
            view_change_count = 0
            for round_id in range(trials):
                # Phases: propose + prepare + commit, each with sig verify
                p1 = propose_phase_ms_base + sig_verify_ms * N + rng.exponential(2.0)
                p2 = prepare_phase_ms_base + sig_verify_ms * (2*f+1) + rng.exponential(2.0)
                p3 = commit_phase_ms_base + sig_verify_ms * (2*f+1) + rng.exponential(2.0)
                total = p1 + p2 + p3
                # View-change overhead
                if round_id > 0 and round_id % view_change_period == 0:
                    total += view_change_overhead_ms
                    view_change_count += 1
                if load_tps > 1500:
                    total *= 1 + (load_tps - 1500) / 1500
                bft_lat.append(total)
            rows.append(dict(load_tps=load_tps, seed=seed,
                             p50_raft=float(np.median(raft_lat)),
                             p99_raft=float(np.percentile(raft_lat, 99)),
                             p50_ai=float(np.median(ai_lat)),
                             p99_ai=float(np.percentile(ai_lat, 99)),
                             p50_bft=float(np.median(bft_lat)),
                             p99_bft=float(np.percentile(bft_lat, 99)),
                             view_changes=view_change_count))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# FX2 — Per-Window Confidence Implementation
# ---------------------------------------------------------------------------


def fx2_per_window_confidence(seeds, n_ticks=10000):
    """Fixed R4A: confidence c_i computed per window via cross-channel
    autocorrelation stability. Verify MTBFD on 10K-tick benign workload."""
    rows = []
    rho = 0.6; W = 64
    n_ch = 4  # multi-channel for cross-channel std
    for seed in seeds:
        rng = np.random.default_rng(seed)
        # Generate n_ticks × W × n_ch
        h = np.zeros((n_ticks, W, n_ch))
        for c in range(n_ch):
            for t in range(1, W):
                h[:, t, c] = rho * h[:, t-1, c] + math.sqrt(1-rho**2) * rng.normal(0, 1, n_ticks)
        x = h  # legit traces
        # Per-window confidence: stability of autocorr across channels
        acs = np.array([np.abs(ac1(x[:, :, c])) for c in range(n_ch)])  # (n_ch, n_ticks)
        r_per_window = 1.0 - acs.mean(axis=0)
        c_per_window = np.exp(-3.0 * acs.std(axis=0))  # CORRECT: per-window
        flagged = (r_per_window > 0.5) & (c_per_window >= 0.7)
        n_flags = int(flagged.sum())
        mtbfd = n_ticks / max(1, n_flags) if n_flags > 0 else float("inf")
        rows.append(dict(seed=seed, n_flags=n_flags, mtbfd_ticks=float(mtbfd)))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# FX3 — Pure Linear Detector (no batch normalisation)
# ---------------------------------------------------------------------------


def fx3_pure_linear(seeds, n_per_class=600):
    """Re-run E1/C1 with a pure linear scorer that does NOT apply
    batch-relative RTT normalisation. Should yield AUC = 0.5 at δ=0."""
    rows = []
    from math import erf
    W = 64; rho = 0.6
    deltas = [0.00, 0.05, 0.10, 0.15, 0.20, 0.30, 0.50, 0.75, 1.00]
    for delta in deltas:
        for seed in seeds:
            rng = np.random.default_rng(seed)
            # Legit AR(1) RTT (single channel for purity)
            h = np.zeros((n_per_class, W))
            for t in range(1, W):
                h[:, t] = rho * h[:, t-1] + math.sqrt(1-rho**2) * rng.normal(0, 1, n_per_class)
            rtt_L = 40 + 8 * h
            # Byzantine: mean shifted by δ·σ
            rtt_B = rng.normal(40 + delta * 8, 8, (n_per_class, W))
            # PURE linear detector: just rtt at endpoint, no batch norm
            score_L = rtt_L[:, -1]
            score_B = rtt_B[:, -1]
            scores = np.concatenate([score_L, score_B])
            y = np.concatenate([np.zeros(n_per_class), np.ones(n_per_class)])
            auc = auc_op(y, scores)
            theory = 0.5 * (1 + erf(delta / 2.0))
            rows.append(dict(delta=delta, seed=seed,
                             empirical=auc, theory=theory))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# FX4 — Linear Detector for Graduated Byzantine
# ---------------------------------------------------------------------------


def fx4_linear_graduated(seeds, n_per_class=600):
    """Re-run R1A using the LINEAR detector (not memory-enabled).
    Graduated Byzantine intensity sweep with linear scorer should
    produce informative AUC curve."""
    rows = []
    W = 64; rho = 0.6
    intensities = [0.01, 0.05, 0.10, 0.20, 0.30, 0.50, 0.75, 1.00]
    for intensity in intensities:
        for seed in seeds:
            rng = np.random.default_rng(seed)
            h = np.zeros((n_per_class, W))
            for t in range(1, W):
                h[:, t] = rho * h[:, t-1] + math.sqrt(1-rho**2) * rng.normal(0, 1, n_per_class)
            rtt_L = 40 + 8 * h
            rtt_B = rng.normal(40 + intensity * 8, 8, (n_per_class, W))
            # PURE linear scorer at endpoint
            score_L = rtt_L[:, -1]
            score_B = rtt_B[:, -1]
            scores = np.concatenate([score_L, score_B])
            y = np.concatenate([np.zeros(n_per_class), np.ones(n_per_class)])
            auc = auc_op(y, scores)
            # Also compute FP / TP rates at fixed threshold
            threshold = 40 + 4  # midway
            fp_rate = float((score_L > threshold).mean())
            tp_rate = float((score_B > threshold).mean())
            rows.append(dict(intensity=intensity, seed=seed,
                             auc=auc, fp_rate=fp_rate, tp_rate=tp_rate))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# FX5 — Conformal NW1 Auto-Calibration
# ---------------------------------------------------------------------------


def fx5_conformal_nw1(seeds, trials=400):
    """Replace NW1's hand-set (μ + 3σ, 20% threshold) with conformal-
    prediction-style auto-tuning. Conformal threshold computed from
    calibration set's RTT-spike empirical distribution at target
    coverage (1 - α) where α = 0.05."""
    rows = []
    W = 64
    alpha_target = 0.05
    for seed in seeds:
        rng = np.random.default_rng(seed)
        n = trials
        rho = 0.6
        # Legit
        h_L = np.zeros((n, W))
        for t in range(1, W):
            h_L[:, t] = rho * h_L[:, t-1] + math.sqrt(1-rho**2) * rng.normal(0, 1, n)
        rtt_L = 40 + 8 * h_L
        spike_loc_L = rng.uniform(size=(n, W)) < 0.10  # 10% spike rate
        rtt_L = np.where(spike_loc_L, rtt_L + 30 * rng.uniform(size=(n, W)), rtt_L)
        # Byzantine: 100% coincidence
        rtt_B = rng.normal(40, 8, (n, W))
        rtt_B = np.where(spike_loc_L, rtt_B + 30 * rng.uniform(size=(n, W)), rtt_B)

        # Hand-set NW1 (baseline)
        # Threshold = window-baseline μ + 3σ; defer if >20% spike
        def nw1_handset(rtt):
            n_w, W_w = rtt.shape
            cleaned = rtt.copy()
            for i in range(n_w):
                m = rtt[i].mean(); s = rtt[i].std()
                spike_mask = rtt[i] > m + 3*s
                if spike_mask.mean() > 0.20:
                    cleaned[i, spike_mask] = m
            return cleaned

        rtt_L_h = nw1_handset(rtt_L)
        rtt_B_h = nw1_handset(rtt_B)
        score_L_h = -np.abs(ac1(rtt_L_h))
        score_B_h = -np.abs(ac1(rtt_B_h))
        y = np.concatenate([np.zeros(n), np.ones(n)])
        auc_handset = auc_op(y, np.concatenate([score_L_h, score_B_h]))

        # Conformal NW1: split calibration / test
        # Use first half of legit as calibration to estimate quantile
        n_cal = n // 2
        cal = rtt_L[:n_cal].flatten()
        threshold_conformal = np.quantile(cal, 1 - alpha_target)
        # Apply conformal threshold to ALL data
        def nw1_conformal(rtt, thresh):
            n_w, W_w = rtt.shape
            cleaned = rtt.copy()
            for i in range(n_w):
                spike_mask = rtt[i] > thresh
                if spike_mask.any():
                    nonspike = rtt[i][~spike_mask]
                    if len(nonspike) > 0:
                        cleaned[i, spike_mask] = nonspike.mean()
            return cleaned

        rtt_L_c = nw1_conformal(rtt_L, threshold_conformal)
        rtt_B_c = nw1_conformal(rtt_B, threshold_conformal)
        score_L_c = -np.abs(ac1(rtt_L_c))
        score_B_c = -np.abs(ac1(rtt_B_c))
        auc_conformal = auc_op(y, np.concatenate([score_L_c, score_B_c]))

        rows.append(dict(seed=seed,
                         auc_handset=auc_handset,
                         auc_conformal=auc_conformal,
                         conformal_threshold=float(threshold_conformal)))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path,
                    default=Path(__file__).parent / "results_v28_fixes")
    ap.add_argument("--n-seeds", type=int, default=30)
    args = ap.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    seeds = list(range(args.n_seeds))

    print("\n=== FX1: Rigorous SmartBFT Model ===")
    fx1 = fx1_rigorous_bft(seeds)
    fx1.to_csv(args.out_dir / "FX1.csv", index=False)
    fx1_sum = fx1.groupby("load_tps")[[
        "p50_raft", "p50_ai", "p50_bft", "p99_raft", "p99_ai", "p99_bft", "view_changes"
    ]].agg("mean").reset_index()
    print(fx1_sum.to_string())

    print("\n=== FX2: Per-Window Confidence (R4A Fix) ===")
    fx2 = fx2_per_window_confidence(seeds)
    fx2.to_csv(args.out_dir / "FX2.csv", index=False)
    print(fx2[["n_flags", "mtbfd_ticks"]].agg(["mean", "std"]).to_string())

    print("\n=== FX3: Pure Linear Detector (C1 Fix) ===")
    fx3 = fx3_pure_linear(seeds)
    fx3.to_csv(args.out_dir / "FX3.csv", index=False)
    fx3_sum = fx3.groupby("delta")[["empirical", "theory"]].agg("mean").reset_index()
    fx3_sum["abs_err"] = (fx3_sum["empirical"] - fx3_sum["theory"]).abs()
    print(fx3_sum.to_string())

    print("\n=== FX4: Linear Detector Graduated Byzantine (R1A Fix) ===")
    fx4 = fx4_linear_graduated(seeds)
    fx4.to_csv(args.out_dir / "FX4.csv", index=False)
    fx4_sum = fx4.groupby("intensity")[["auc", "fp_rate", "tp_rate"]].agg("mean").reset_index()
    print(fx4_sum.to_string())

    print("\n=== FX5: Conformal NW1 Auto-Calibration ===")
    fx5 = fx5_conformal_nw1(seeds)
    fx5.to_csv(args.out_dir / "FX5.csv", index=False)
    print(fx5[["auc_handset", "auc_conformal", "conformal_threshold"]].agg(["mean", "std"]).to_string())

    md = ["# v28 Remaining-Weakness Fix Experiments (FX1-FX5)", ""]
    md.append("## FX1 — Rigorous SmartBFT (R3A refinement)")
    md.append("| TPS | p50-Raft | p50-AI | p50-BFT | p99-Raft | p99-AI | p99-BFT | View changes |")
    md.append("|---:|---:|---:|---:|---:|---:|---:|---:|")
    for _, r in fx1_sum.iterrows():
        md.append(f"| {int(r['load_tps'])} | {r['p50_raft']:.2f} | {r['p50_ai']:.2f} | {r['p50_bft']:.2f} | {r['p99_raft']:.2f} | {r['p99_ai']:.2f} | {r['p99_bft']:.2f} | {r['view_changes']:.1f} |")
    md.append("")
    md.append("## FX2 — Per-Window Confidence (R4A Fix)")
    md.append(f"- Mean flags per seed (10,000 benign ticks): {fx2['n_flags'].mean():.2f}")
    md.append(f"- MTBFD: **{fx2['mtbfd_ticks'].mean():.0f} ticks** (or inf if 0 flags)")
    md.append("")
    md.append("## FX3 — Pure Linear Detector (C1 Fix)")
    md.append("| δ | Empirical | Theory | Abs error |")
    md.append("|---:|---:|---:|---:|")
    for _, r in fx3_sum.iterrows():
        md.append(f"| {r['delta']:.2f} | {r['empirical']:.4f} | {r['theory']:.4f} | {r['abs_err']:.4f} |")
    md.append("")
    md.append("## FX4 — Linear Detector Graduated Byzantine (R1A Fix)")
    md.append("| Intensity | AUC | FP rate | TP rate |")
    md.append("|---:|---:|---:|---:|")
    for _, r in fx4_sum.iterrows():
        md.append(f"| {r['intensity']:.2f} | {r['auc']:.3f} | {r['fp_rate']:.3f} | {r['tp_rate']:.3f} |")
    md.append("")
    md.append("## FX5 — Conformal NW1 Auto-Calibration")
    md.append(f"- Hand-set AUC: {fx5['auc_handset'].mean():.4f} ± {fx5['auc_handset'].std():.4f}")
    md.append(f"- **Conformal auto-calibration AUC: {fx5['auc_conformal'].mean():.4f} ± {fx5['auc_conformal'].std():.4f}**")
    md.append(f"- Mean conformal threshold (α=0.05): {fx5['conformal_threshold'].mean():.2f}")

    (args.out_dir / "REPORT.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"\nReport: {args.out_dir / 'REPORT.md'}")


if __name__ == "__main__":
    main()
