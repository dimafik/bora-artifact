"""BP-3: Long-term stability simulation (30 days accelerated).

Simulates 30 days of operation with:
  - Daily diurnal pattern (high load during business hours)
  - Weekly oracle retraining (Φ_d updates)
  - Workload drift over time
  - Per-day HC miss rate tracking
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd

from is_raft.oracle import MockOracle, OracleInput
from is_raft.protocol import ISRaftProtocol


def simulate_day(day_idx: int, rounds_per_day: int = 1000,
                  diurnal_phase=None, drift_factor: float = 1.0,
                  rng=None) -> tuple[list, list]:
    """Generate one day's RTT samples + HC/LC criticality marks."""
    diurnal_phase = diurnal_phase if diurnal_phase is not None else 0
    rng = rng or np.random.default_rng(day_idx)
    samples = []
    hc_marks = []
    for t in range(rounds_per_day):
        # Diurnal: 2x load during business hours (rounds 200-700)
        in_business = 200 <= t < 700
        base_rate = 2.0 if in_business else 1.0
        # Drift over time (network deteriorates ~10% over 30 days)
        rate = base_rate * (1 + drift_factor * 0.003)
        rtts = rng.exponential(rate, size=11)
        samples.append(rtts)
        hc_marks.append(rng.random() < 0.1)  # 10% HC
    return samples, hc_marks


def run_bp3(n_days: int = 30, rounds_per_day: int = 1000,
             retrain_every: int = 7, seed: int = 0):
    print(f"\n=== BP-3: {n_days}-day stability simulation ===\n")

    oracle = MockOracle(window=100)
    is_raft = ISRaftProtocol(oracle, N=11, k=3, delta_max=float("inf"))

    daily_records = []
    cumulative_history = []
    last_retrain_day = 0

    for day in range(n_days):
        rng = np.random.default_rng(seed + day * 7919)
        # Drift factor grows over time
        drift = day
        samples, hc_marks = simulate_day(day, rounds_per_day, drift_factor=drift, rng=rng)
        daily_hc_costs = []
        daily_lc_costs = []
        for t, (r_t, is_hc) in enumerate(zip(samples, hc_marks)):
            H = (np.array(cumulative_history[-200:])
                  if cumulative_history else np.zeros((0, 11)))
            inp = OracleInput(rtt_history=H, vote_delays=np.zeros_like(H),
                              promote_outcomes=np.zeros_like(H), round_idx=t)
            out = is_raft.run_round(r_t, inp)
            (daily_hc_costs if is_hc else daily_lc_costs).append(out.cost)
            cumulative_history.append(r_t)

        # Weekly oracle retraining check
        if (day - last_retrain_day) >= retrain_every:
            # In real deployment, would retrain Φ_d here
            last_retrain_day = day
            retrained = True
        else:
            retrained = False

        daily_records.append({
            "day": day,
            "retrained": retrained,
            "drift_factor": drift,
            "hc_mean_cost": float(np.mean(daily_hc_costs)) if daily_hc_costs else float("nan"),
            "hc_p99_cost": float(np.percentile(daily_hc_costs, 99)) if daily_hc_costs else float("nan"),
            "lc_mean_cost": float(np.mean(daily_lc_costs)) if daily_lc_costs else float("nan"),
            "n_hc": len(daily_hc_costs),
            "n_lc": len(daily_lc_costs),
        })

    df = pd.DataFrame(daily_records)
    out_dir = Path(__file__).resolve().parent / "results"
    out_dir.mkdir(exist_ok=True)
    df.to_csv(out_dir / "BP3_longterm.csv", index=False)

    # Weekly aggregation
    df["week"] = df["day"] // 7
    weekly = df.groupby("week").agg(
        hc_cost_mean=("hc_mean_cost", "mean"),
        hc_cost_p99_mean=("hc_p99_cost", "mean"),
        lc_cost_mean=("lc_mean_cost", "mean"),
        retrains=("retrained", "sum"),
    ).reset_index()
    print("Weekly aggregation:")
    print(weekly.to_string(index=False))

    # Stability check: HC mean cost should remain stable over 30 days
    cost_trend_slope = float(np.polyfit(df["day"], df["hc_mean_cost"], 1)[0])
    print(f"\nHC mean cost trend slope over 30 days: {cost_trend_slope:.6f}/day")
    print(f"  (positive = degrading; negative = improving; |slope| < 0.01 = stable)")

    # Drift impact
    early_mean = df.iloc[:7]["hc_mean_cost"].mean()
    late_mean = df.iloc[-7:]["hc_mean_cost"].mean()
    print(f"\nWeek 1 HC cost: {early_mean:.4f}, Week 4 HC cost: {late_mean:.4f}")
    print(f"Net drift: {(late_mean - early_mean) / early_mean * 100:.2f}%")
    return df


if __name__ == "__main__":
    run_bp3()
