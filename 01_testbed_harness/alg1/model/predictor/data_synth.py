"""
data_synth.py -- Synthetic S-Raft trace generator for predictor training.

Generates per-node time series of (cc, CC, rtt, RTT, T_commit, dCC, dRTT, design)
plus three ground-truth labels:

  - Score @ horizons H = {30s, 60s, 90s} (computed via S-Raft's exact formula)
  - Byzantine flag (true if node was in injected adversarial mode)
  - Degradation flag (true if a timer overshoot happened within next 1h)

The simulator is light and runs entirely in numpy/pandas; no Fabric or Raft
binary required.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

# =============================================================================
# S-Raft constants (from v5_3 paper, locked)
# =============================================================================

W = 100                    # commit-contribution window
ALPHA = 0.8                # RTT EMA smoothing
W_CC = 0.6
W_RTT = 0.4
HYSTERESIS = 0.05
HEARTBEAT_MS = 50          # tick interval
T_FOLLOWER_MAX_MS = 280    # max follower timer

# Predictor horizons in ticks (heartbeat = 50ms)
H_TICKS = {30: 600, 60: 1200, 90: 1800}   # 30/60/90 seconds


# =============================================================================
# Per-node baseline parameters
# =============================================================================


@dataclass
class NodeProfile:
    base_ack_lat_ms: float       # mean ack latency baseline
    ack_jitter_ms: float         # std of per-tick ack noise
    base_rtt_ms: float
    rtt_jitter_ms: float
    drop_prob: float = 0.0       # probability of missing ack (counts as not-in-window)
    byzantine: bool = False      # if True, fakes ack but skips commit
    degrade_at_tick: int = -1    # if >=0, GC stall begins here
    degrade_duration_ticks: int = 0
    degrade_lat_multiplier: float = 4.0


def random_profile(rng: np.random.Generator, baseline_class: str = "healthy") -> NodeProfile:
    if baseline_class == "healthy":
        return NodeProfile(
            base_ack_lat_ms=float(rng.uniform(20, 60)),
            ack_jitter_ms=float(rng.uniform(3, 8)),
            base_rtt_ms=float(rng.uniform(2, 15)),
            rtt_jitter_ms=float(rng.uniform(0.5, 2.5)),
            drop_prob=float(rng.uniform(0.0, 0.02)),
        )
    elif baseline_class == "noisy":
        return NodeProfile(
            base_ack_lat_ms=float(rng.uniform(60, 120)),
            ack_jitter_ms=float(rng.uniform(15, 35)),
            base_rtt_ms=float(rng.uniform(15, 60)),
            rtt_jitter_ms=float(rng.uniform(3, 12)),
            drop_prob=float(rng.uniform(0.01, 0.06)),
        )
    elif baseline_class == "byzantine":
        return NodeProfile(
            base_ack_lat_ms=float(rng.uniform(15, 25)),  # too good to be true
            ack_jitter_ms=float(rng.uniform(1, 3)),
            base_rtt_ms=float(rng.uniform(2, 5)),
            rtt_jitter_ms=float(rng.uniform(0.2, 0.8)),
            drop_prob=0.0,
            byzantine=True,
        )
    else:
        raise ValueError(baseline_class)


# =============================================================================
# Single-node trace generator
# =============================================================================


def gen_node_trace(
    profile: NodeProfile,
    n_ticks: int,
    rng: np.random.Generator,
    leader_t_commit_series: np.ndarray,
) -> pd.DataFrame:
    """Generate raw per-tick measurements for one node."""
    ack_lats = np.empty(n_ticks)
    rtts = np.empty(n_ticks)
    drops = np.zeros(n_ticks, dtype=bool)

    # Generate ack/rtt time series.
    # Legit nodes have AR(1) autocorrelation (rho_ar=0.6) from process
    # scheduling; Byzantine attackers generating IID samples lack this.
    rho_ar = 0.0 if profile.byzantine else 0.6
    eps_ack = rng.normal(0, profile.ack_jitter_ms, n_ticks)
    eps_rtt = rng.normal(0, profile.rtt_jitter_ms, n_ticks)
    ack_noise = np.empty(n_ticks); ack_noise[0] = eps_ack[0]
    rtt_noise = np.empty(n_ticks); rtt_noise[0] = eps_rtt[0]
    for t in range(1, n_ticks):
        ack_noise[t] = rho_ar * ack_noise[t-1] + np.sqrt(1 - rho_ar**2) * eps_ack[t]
        rtt_noise[t] = rho_ar * rtt_noise[t-1] + np.sqrt(1 - rho_ar**2) * eps_rtt[t]

    degraded_flag = np.zeros(n_ticks, dtype=bool)
    for t in range(n_ticks):
        mult = 1.0
        if profile.degrade_at_tick >= 0 \
           and profile.degrade_at_tick <= t < profile.degrade_at_tick + profile.degrade_duration_ticks:
            mult = profile.degrade_lat_multiplier
            degraded_flag[t] = True

        ack_lats[t] = max(0.5, profile.base_ack_lat_ms * mult + ack_noise[t])
        rtts[t]     = max(0.5, profile.base_rtt_ms * mult + rtt_noise[t])
        drops[t]    = rng.random() < profile.drop_prob

    # Compute CC and RTT EMA
    cc_instant = (ack_lats <= leader_t_commit_series) & (~drops)
    cc = pd.Series(cc_instant.astype(float)).rolling(W, min_periods=1).mean().to_numpy()

    rtt_ema = np.empty(n_ticks)
    rtt_ema[0] = rtts[0]
    for t in range(1, n_ticks):
        rtt_ema[t] = ALPHA * rtt_ema[t - 1] + (1 - ALPHA) * rtts[t]

    return pd.DataFrame({
        "tick":         np.arange(n_ticks),
        "cc_inst":      cc_instant.astype(float),
        "CC":           cc,
        "rtt":          rtts,
        "RTT":          rtt_ema,
        "T_commit":     leader_t_commit_series,
        "degraded":     degraded_flag,
    })


def compute_score(df: pd.DataFrame, rtt_global_min: float, rtt_global_max: float) -> np.ndarray:
    """S-Raft score formula (Eq. derived from v5_3 §III-B)."""
    denom = rtt_global_max - rtt_global_min + 1e-9
    rtt_norm = np.clip((rtt_global_max - df["RTT"].to_numpy()) / denom, 0.0, 1.0)
    return W_CC * df["CC"].to_numpy() + W_RTT * rtt_norm


# =============================================================================
# Trace assembly (per cluster scenario)
# =============================================================================


def gen_trace(
    n_nodes: int,
    n_ticks: int,
    seed: int,
    scenario: str,
) -> dict:
    rng = np.random.default_rng(seed)

    # T_commit series: rolling 90th percentile of ack latencies across all nodes
    # For simulator simplicity, use a calm baseline + occasional spikes
    base_t_commit = 80.0
    t_commit_series = base_t_commit + rng.normal(0, 4, n_ticks).cumsum() * 0.01
    t_commit_series = np.clip(t_commit_series, 50, 150)

    # Build profiles per scenario
    profiles = []
    byz_idx = []
    deg_idx = []
    if scenario == "clean":
        profiles = [random_profile(rng, "healthy") for _ in range(n_nodes)]
    elif scenario == "noisy":
        profiles = [random_profile(rng, "noisy") for _ in range(n_nodes)]
    elif scenario == "byzantine":
        # 1 byzantine node
        byz_idx = [int(rng.integers(0, n_nodes))]
        for i in range(n_nodes):
            if i in byz_idx:
                profiles.append(random_profile(rng, "byzantine"))
            else:
                profiles.append(random_profile(rng, "healthy"))
    elif scenario == "degrade":
        deg_idx = [int(rng.integers(0, n_nodes))]
        for i in range(n_nodes):
            p = random_profile(rng, "healthy")
            if i in deg_idx:
                p.degrade_at_tick = int(rng.integers(n_ticks // 4, n_ticks * 3 // 4))
                p.degrade_duration_ticks = int(rng.integers(600, 1800))
            profiles.append(p)
    else:
        raise ValueError(scenario)

    node_dfs = [gen_node_trace(p, n_ticks, rng, t_commit_series) for p in profiles]

    # Score per node per tick
    all_rtt = np.concatenate([df["RTT"].to_numpy() for df in node_dfs])
    rtt_min, rtt_max = float(all_rtt.min()), float(all_rtt.max())
    for df in node_dfs:
        df["Score"] = compute_score(df, rtt_min, rtt_max)
        df["dCC"] = df["CC"].diff().fillna(0.0)
        df["dRTT"] = df["RTT"].diff().fillna(0.0)

    return {
        "scenario":         scenario,
        "n_nodes":          n_nodes,
        "n_ticks":          n_ticks,
        "seed":             seed,
        "rtt_min":          rtt_min,
        "rtt_max":          rtt_max,
        "byzantine_nodes":  byz_idx,
        "degrade_nodes":    deg_idx,
        "node_traces":      node_dfs,
    }


# =============================================================================
# Windowed dataset construction
# =============================================================================


def make_windows(trace: dict, window_len: int = 60, stride: int = 30) -> tuple[np.ndarray, pd.DataFrame]:
    """
    Slice each node's trace into windows.
    Returns:
        x_array: (N, window_len, 8) float32
        labels:  DataFrame with score/anomaly/degrade per row
    """
    xs = []
    rows = []
    n_ticks = trace["n_ticks"]
    horizons = sorted(H_TICKS.values())   # 600, 1200, 1800
    H_MAX = horizons[-1]

    for node_idx, df in enumerate(trace["node_traces"]):
        is_byz = int(node_idx in trace["byzantine_nodes"])
        for start in range(0, n_ticks - window_len - H_MAX, stride):
            window_end = start + window_len

            x = df.iloc[start:window_end][
                ["cc_inst", "CC", "rtt", "RTT", "T_commit", "dCC", "dRTT"]
            ].to_numpy()

            # Designation channel: simplistic -- first 2 nodes are P/S
            design = np.zeros((window_len, 1))
            if node_idx == 0: design[:] = 1.0   # primary
            elif node_idx == 1: design[:] = 0.5  # secondary

            x_full = np.concatenate([x, design], axis=1).astype(np.float32)  # (60, 8)
            xs.append(x_full)

            # Score labels @ horizons
            score_labels = []
            for h in horizons:
                idx = min(window_end + h - 1, n_ticks - 1)
                score_labels.append(float(df["Score"].iloc[idx]))

            # Degradation label: ground-truth flag from node profile,
            # avoiding noisy RTT-threshold heuristic that under-fires.
            deg_window = df.iloc[window_end : min(window_end + 72000, n_ticks)]
            is_deg = int(deg_window["degraded"].any()) if "degraded" in deg_window.columns else 0

            rows.append({
                "score_30s": score_labels[0],
                "score_60s": score_labels[1],
                "score_90s": score_labels[2],
                "byzantine": is_byz,
                "degrade":   is_deg,
                "node_idx":  node_idx,
                "scenario":  trace["scenario"],
                "seed":      trace["seed"],
            })

    return np.stack(xs).astype(np.float32), pd.DataFrame(rows)


# =============================================================================
# CLI
# =============================================================================


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--n-traces", type=int, default=80)
    ap.add_argument("--n-nodes", type=int, default=5)
    ap.add_argument("--n-ticks", type=int, default=20000)  # 1000s @ 50ms tick
    ap.add_argument("--seed-offset", type=int, default=0)
    args = ap.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    scenarios = ["clean", "noisy", "byzantine", "degrade"]
    summary = []

    for s_i, scenario in enumerate(scenarios):
        for k in range(args.n_traces):
            seed = args.seed_offset + s_i * 1000 + k
            tr = gen_trace(args.n_nodes, args.n_ticks, seed, scenario)
            x_arr, df = make_windows(tr)
            xs_file = args.out_dir / f"{scenario}_seed{seed:04d}.npy"
            lbl_file = args.out_dir / f"{scenario}_seed{seed:04d}.parquet"
            np.save(xs_file, x_arr)
            df.to_parquet(lbl_file)
            summary.append({
                "scenario": scenario,
                "seed":     seed,
                "n_windows": len(df),
                "xs_file":  xs_file.name,
                "labels_file": lbl_file.name,
            })

    summary_df = pd.DataFrame(summary)
    summary_df.to_csv(args.out_dir / "manifest.csv", index=False)

    print(f"Generated {len(summary)} traces, "
          f"total {sum(s['n_windows'] for s in summary):,} windows")
    print(f"Output: {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
