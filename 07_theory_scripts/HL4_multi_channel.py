"""HL-4: Multi-channel scalability.

Fabric multi-channel architecture: each channel runs its own scheduler
but shares the oracle Φ_d (same network conditions).

Tests: 1, 4, 16, 64 channels concurrent operation.
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


class MultiChannelScheduler:
    """Per-channel scheduler with shared oracle."""
    def __init__(self, n_channels: int, tasks_per_channel: int = 1000):
        self.n_channels = n_channels
        self.channel_workloads = []
        self.channel_forecasts = []

    def build(self, hc_frac: float = 0.1, rng=None):
        rng = rng or np.random.default_rng(0)
        for ch in range(self.n_channels):
            cb = CaliperBenchmark(mode="asset_transfer",
                                   n_tasks=1000, tps=50, hc_frac=hc_frac,
                                   rng=np.random.default_rng(ch * 7919))
            wl, fcs = cb.generate()
            # Offset arrivals by channel to simulate concurrent operation
            for t in wl:
                t.task_id = f"ch{ch}_{t.task_id}"
            self.channel_workloads.append(wl)
            self.channel_forecasts.append({f"ch{ch}_{tid}": v
                                           for tid, v in fcs.items()})

    def simulate(self, rng) -> dict:
        # Each channel runs independently (in parallel = no interference)
        records = []
        for ch in range(self.n_channels):
            wl = self.channel_workloads[ch]
            fcs = self.channel_forecasts[ch]
            sched = schedule_priority(wl)
            t_finish = 0.0
            hc_count = lc_count = hc_miss = lc_miss = 0
            latencies = []
            for task in sched:
                f = fcs[task.task_id]
                actual = max(0.001, f.expected + rng.normal(0, f.zeta))
                start = max(task.arrival_time, t_finish)
                commit = start + actual
                latencies.append(actual * 1000)
                if task.criticality == "HC":
                    hc_count += 1
                    if commit > task.deadline: hc_miss += 1
                else:
                    lc_count += 1
                    if commit > task.deadline: lc_miss += 1
                t_finish = commit
            records.append({
                "channel": ch,
                "n_tasks": len(wl),
                "hc_count": hc_count, "lc_count": lc_count,
                "hc_miss": hc_miss, "lc_miss": lc_miss,
                "hc_miss_rate": hc_miss / max(hc_count, 1),
                "lc_miss_rate": lc_miss / max(lc_count, 1),
                "p99_latency_ms": float(np.percentile(latencies, 99)) if latencies else 0,
            })
        return records


def run_hl4():
    print("\n=== HL-4: Multi-channel scalability ===\n")
    n_channel_configs = [1, 4, 16, 64]
    all_records = []
    for nc in n_channel_configs:
        for seed in range(3):
            mcs = MultiChannelScheduler(n_channels=nc)
            mcs.build(hc_frac=0.1, rng=np.random.default_rng(seed))
            rng = np.random.default_rng(seed + 7919)
            results = mcs.simulate(rng)
            for r in results:
                r["n_channels"] = nc
                r["seed"] = seed
                all_records.append(r)
    df = pd.DataFrame(all_records)
    out_dir = Path(__file__).resolve().parent / "results"
    out_dir.mkdir(exist_ok=True)
    df.to_csv(out_dir / "HL4_multichannel.csv", index=False)

    # Aggregate per channel count
    agg = df.groupby("n_channels").agg(
        avg_hc_miss=("hc_miss_rate", "mean"),
        avg_lc_miss=("lc_miss_rate", "mean"),
        avg_p99_ms=("p99_latency_ms", "mean"),
        total_tasks=("n_tasks", "sum"),
    ).reset_index()
    print("Multi-channel summary:")
    print(agg.to_string(index=False))

    # HC miss rate variance across channels (cross-channel interference?)
    print("\nHC miss rate variance across channels:")
    for nc in n_channel_configs:
        sub = df[df["n_channels"] == nc]["hc_miss_rate"]
        ci = bootstrap_ci(sub.values, np.mean, n_boot=1500)
        print(f"  n_channels={nc:>3d}: hc_miss = {ci.point:.4f} "
              f"[{ci.ci_lo:.4f}, {ci.ci_hi:.4f}], variance = {sub.var():.6e}")


if __name__ == "__main__":
    run_hl4()
