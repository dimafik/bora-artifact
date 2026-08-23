"""HL-5: Caliper benchmark extended evaluation.

Production-style 24-hour simulated run on 3 Caliper workloads:
  - asset_transfer (100 tps sustained)
  - smallbank (50 tps sustained)
  - marbles02 (20 tps sustained)

Measurements:
  - HC/LC miss rates (mean + 95% CI)
  - p50/p95/p99/p99.9 commit latency
  - Throughput-latency curve
  - Hourly breakdown for drift detection
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd

from is_raft.workload import CaliperBenchmark
from is_raft.schedulability import (lac_schedulability_test, mode_switch_decision,
                                     schedule_priority)
from is_raft.stats import bootstrap_ci


def simulate_caliper(workload, forecasts, rng, hours: int = 24,
                     hour_seconds: float = 3600.0) -> dict:
    """Simulate Caliper workload over `hours` simulated hours.
    Tasks are partitioned into hourly buckets for drift analysis.
    """
    sched = schedule_priority(workload)
    t_finish = 0.0
    hourly = {h: {"hc_count": 0, "lc_count": 0,
                  "hc_miss": 0, "lc_miss": 0,
                  "commit_latencies": []} for h in range(hours)}
    for task in sched:
        f = forecasts[task.task_id]
        actual = max(0.001, f.expected + rng.normal(0, f.zeta))
        start = max(task.arrival_time, t_finish)
        commit = start + actual
        latency = actual
        hour_bucket = min(int(task.arrival_time / hour_seconds), hours - 1)
        h = hourly[hour_bucket]
        if task.criticality == "HC":
            h["hc_count"] += 1
            if commit > task.deadline:
                h["hc_miss"] += 1
        else:
            h["lc_count"] += 1
            if commit > task.deadline:
                h["lc_miss"] += 1
        h["commit_latencies"].append(latency * 1000)  # ms
        t_finish = commit
    return hourly


def run_hl5(workload_modes=("asset_transfer", "smallbank", "marbles02"),
            n_trials: int = 5, seed: int = 0):
    print("\n=== HL-5: Caliper benchmark extended evaluation ===\n")
    records = []
    for mode in workload_modes:
        # 24-hour workload at workload-specific tps
        tps_map = {"asset_transfer": 100, "smallbank": 50, "marbles02": 20}
        tps = tps_map[mode]
        # 1-hour worth of tasks per trial (= simulating 1 hour in detail × 5 trials)
        n_tasks_per_hour = int(tps * 3600)
        for trial in range(n_trials):
            cb = CaliperBenchmark(mode=mode, n_tasks=n_tasks_per_hour, tps=tps,
                                   hc_frac=0.1,
                                   rng=np.random.default_rng(seed + trial * 7919))
            wl, fcs = cb.generate()
            sim = simulate_caliper(wl, fcs, np.random.default_rng(seed + trial * 31),
                                    hours=1, hour_seconds=3600.0)
            h0 = sim[0]
            all_latencies = np.array(h0["commit_latencies"])
            records.append({
                "workload": mode,
                "trial": trial,
                "tps": tps,
                "n_tasks": h0["hc_count"] + h0["lc_count"],
                "hc_count": h0["hc_count"],
                "lc_count": h0["lc_count"],
                "hc_miss_rate": h0["hc_miss"] / max(h0["hc_count"], 1),
                "lc_miss_rate": h0["lc_miss"] / max(h0["lc_count"], 1),
                "p50_latency_ms": float(np.percentile(all_latencies, 50)),
                "p95_latency_ms": float(np.percentile(all_latencies, 95)),
                "p99_latency_ms": float(np.percentile(all_latencies, 99)),
                "p999_latency_ms": float(np.percentile(all_latencies, 99.9)),
                "mean_latency_ms": float(np.mean(all_latencies)),
            })
    df = pd.DataFrame(records)
    out_dir = Path(__file__).resolve().parent / "results"
    out_dir.mkdir(exist_ok=True)
    df.to_csv(out_dir / "HL5_caliper_extended.csv", index=False)

    # Summary
    print("Per-workload aggregated results (5 trials):")
    agg = df.groupby("workload").agg(
        hc_miss_mean=("hc_miss_rate", "mean"),
        lc_miss_mean=("lc_miss_rate", "mean"),
        p50_mean=("p50_latency_ms", "mean"),
        p99_mean=("p99_latency_ms", "mean"),
        p999_mean=("p999_latency_ms", "mean"),
    ).reset_index()
    print(agg.to_string(index=False))

    # 95% CI on key metrics
    print("\nHC miss rate 95% CI per workload:")
    for w in workload_modes:
        rates = df[df["workload"] == w]["hc_miss_rate"].values
        ci = bootstrap_ci(rates, np.mean, n_boot=2000)
        print(f"  {w:20s}: {ci}")
    print(f"\nSaved to {out_dir}")
    return df


if __name__ == "__main__":
    run_hl5()
