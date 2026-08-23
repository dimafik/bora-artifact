"""NV-1: Compare 4 scheduler variants on a Caliper-style workload.

This experiment seeds Paper-2 (Mode-Switching Consensus) follow-up.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd

from is_raft.workload import CaliperBenchmark
from is_raft.scheduler_variants import compare_schedulers
from is_raft.stats import bootstrap_ci


def run_nv1(n_trials: int = 10, seed: int = 0):
    print("\n=== NV-1: Scheduler Variants Comparison ===\n")
    records = []
    for trial in range(n_trials):
        cb = CaliperBenchmark(mode="smallbank", n_tasks=500, tps=50, hc_frac=0.2,
                               rng=np.random.default_rng(seed + trial))
        wl, fcs = cb.generate()
        results = compare_schedulers(wl, fcs,
                                      rng=np.random.default_rng(seed + trial * 31))
        for name, r in results.items():
            records.append({
                "trial": trial, "scheduler": name,
                **r,
            })
    df = pd.DataFrame(records)
    out = Path(__file__).resolve().parent / "results" / "NV1_scheduler_variants.csv"
    out.parent.mkdir(exist_ok=True)
    df.to_csv(out, index=False)

    print("Per-scheduler aggregated results (10 trials):")
    agg = df.groupby("scheduler").agg(
        hc_miss_mean=("hc_miss_rate", "mean"),
        lc_miss_mean=("lc_miss_rate", "mean"),
        total_misses_mean=("total_misses", "mean"),
    ).reset_index()
    print(agg.to_string(index=False))

    print("\n95% CI on HC miss rate:")
    for name in df["scheduler"].unique():
        rates = df[df["scheduler"] == name]["hc_miss_rate"].values
        ci = bootstrap_ci(rates, np.mean, n_boot=2000)
        print(f"  {name:25s}: {ci}")


if __name__ == "__main__":
    run_nv1()
