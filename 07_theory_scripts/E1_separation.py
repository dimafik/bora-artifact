"""Experiment E1 — Theorem A: Classical vs LAC separation under heavy-tail.

Sweeps Pareto shape α ∈ {0.8, 1.0, 1.2, 1.5, 2.0, 3.0} for two RTT regimes
(stationary and non-stationary), measures:
    - Baseline (RTT-min over history): cost grows ~ N^{1/α}
    - IS-Raft with PerfectOracle: cost = O(1)
Output: separation gap CSV + plot data for Fig. 1 (Theorem A verification).
"""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from is_raft.distributions import StationaryPareto, NonStationaryHeavyTail
from is_raft.oracle import PerfectOracle, MockOracle, OracleInput
from is_raft.protocol import ISRaftProtocol, BaselineRaftProtocol


def run_separation_sweep(N: int = 11, n_rounds: int = 500, history_len: int = 100,
                         alphas=(0.8, 1.0, 1.2, 1.5, 2.0, 3.0),
                         seed: int = 0):
    rng = np.random.default_rng(seed)
    records = []
    for regime in ("stationary", "nonstationary"):
        for alpha in alphas:
            if regime == "stationary":
                dist = StationaryPareto(N=N, r_min=1.0, alpha=alpha, rng=rng)
            else:
                dist = NonStationaryHeavyTail(N=N, alpha=alpha,
                                              shift_period=50, rng=rng)
            oracle_perfect = PerfectOracle(dist)
            oracle_mock = MockOracle(window=50)
            baseline = BaselineRaftProtocol(N=N, k=3)
            isr_perfect = ISRaftProtocol(oracle_perfect, N=N, k=3)
            isr_mock = ISRaftProtocol(oracle_mock, N=N, k=3)

            history = []
            costs = {"baseline": [], "is_raft_perfect": [], "is_raft_mock": []}

            for t in range(n_rounds):
                r_t = dist.sample(t)
                hist_arr = np.array(history[-history_len:]) if history else np.zeros((0, N))
                hist_input = OracleInput(
                    rtt_history=hist_arr,
                    vote_delays=np.zeros_like(hist_arr),
                    promote_outcomes=np.zeros_like(hist_arr),
                    round_idx=t,
                )
                o_b = baseline.run_round(r_t, hist_input)
                o_p = isr_perfect.run_round(r_t, hist_input)
                o_m = isr_mock.run_round(r_t, hist_input)
                costs["baseline"].append(o_b.cost)
                costs["is_raft_perfect"].append(o_p.cost)
                costs["is_raft_mock"].append(o_m.cost)
                history.append(r_t)

            for key in costs:
                records.append({
                    "regime": regime,
                    "alpha": alpha,
                    "protocol": key,
                    "N": N,
                    "mean_cost": np.mean(costs[key]),
                    "p50_cost": np.median(costs[key]),
                    "p95_cost": np.percentile(costs[key], 95),
                    "n_rounds": n_rounds,
                })
    df = pd.DataFrame(records)
    # Compute separation gap
    base = df[df["protocol"] == "baseline"].set_index(["regime", "alpha"])["mean_cost"]
    perf = df[df["protocol"] == "is_raft_perfect"].set_index(["regime", "alpha"])["mean_cost"]
    mock = df[df["protocol"] == "is_raft_mock"].set_index(["regime", "alpha"])["mean_cost"]
    gap_df = pd.DataFrame({
        "baseline": base,
        "is_raft_perfect": perf,
        "is_raft_mock": mock,
        "gap_perfect": base / perf,
        "gap_mock": base / mock,
    }).reset_index()
    return df, gap_df


if __name__ == "__main__":
    df, gap_df = run_separation_sweep()
    out_dir = Path(__file__).resolve().parent / "results"
    out_dir.mkdir(exist_ok=True)
    df.to_csv(out_dir / "E1_raw.csv", index=False)
    gap_df.to_csv(out_dir / "E1_gap.csv", index=False)
    print("\n=== E1 Separation Gap (Theorem A verification) ===")
    print(gap_df.to_string(index=False))
    print(f"\nSaved to {out_dir}")
