"""F5 — Evaluation of LAC on RWA-shaped + Caliper workloads (§11).

Runs schedulability test + simulation on each workload type to produce
Table 2 of paper: HC miss rate, LC miss rate, mode-switch frequency.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd

from is_raft.schedulability import lac_schedulability_test, mode_switch_decision, schedule_priority
from is_raft.workload import (CaliperBenchmark, TradeLensWorkload, MarcoPoloWorkload,
                              B3iWorkload, CBDCWorkload, BurstyWorkload)
from is_raft.stats import bootstrap_ci


def simulate_with_modes(workload, forecasts, rng, slack_guard: float = 0.5):
    """Simulate execution with mode-switching (Thm 3).
    In CRITICAL mode, only HC tasks proceed."""
    sched = schedule_priority(workload)
    t_finish = 0.0
    hc_misses = lc_misses = 0
    hc_count = sum(1 for t in workload if t.criticality == "HC")
    lc_count = sum(1 for t in workload if t.criticality == "LC")
    mode_history = []
    # Sample mode periodically to avoid O(N^2)
    mode_cache = {}
    for ti, task in enumerate(sched):
        # Recompute mode every 50 tasks (or 1 if HC)
        bucket = ti // 50
        if bucket not in mode_cache:
            remaining = [t for t in workload if t.arrival_time >= task.arrival_time]
            mode_cache[bucket] = mode_switch_decision(remaining[:30], forecasts, N=11,
                                                       slack_guard=slack_guard)
        mode = mode_cache[bucket]
        mode_history.append(mode)
        if mode == "CRITICAL" and task.criticality == "LC":
            # Suspend LC under CRITICAL
            continue
        f = forecasts[task.task_id]
        actual = max(0.001, f.expected + rng.normal(0, f.zeta))
        start = max(task.arrival_time, t_finish)
        commit = start + actual
        if commit > task.deadline:
            if task.criticality == "HC":
                hc_misses += 1
            else:
                lc_misses += 1
        t_finish = commit
    return {
        "hc_count": hc_count, "lc_count": lc_count,
        "hc_misses": hc_misses, "lc_misses": lc_misses,
        "hc_miss_rate": hc_misses / max(hc_count, 1),
        "lc_miss_rate": lc_misses / max(lc_count, 1),
        "critical_fraction": sum(1 for m in mode_history if m == "CRITICAL") / max(len(mode_history), 1),
    }


def run_workload_eval(workload_factory, name: str, n_trials: int = 5,
                       seed: int = 0):
    records = []
    for trial in range(n_trials):
        wl, fcs = workload_factory(seed + trial)
        sched_result = lac_schedulability_test(wl, fcs, N=11, delta=0.05)
        sim = simulate_with_modes(wl, fcs,
                                   rng=np.random.default_rng(seed + 7919 + trial))
        records.append({
            "workload": name, "trial": trial,
            "n_tasks": len(wl),
            "test_decision": sched_result.decision,
            "hc_miss_rate": sim["hc_miss_rate"],
            "lc_miss_rate": sim["lc_miss_rate"],
            "critical_fraction": sim["critical_fraction"],
            "hc_count": sim["hc_count"], "lc_count": sim["lc_count"],
        })
    return pd.DataFrame(records)


if __name__ == "__main__":
    factories = [
        ("Caliper-asset_transfer", lambda s: CaliperBenchmark(
            mode="asset_transfer", n_tasks=500, tps=50,
            rng=np.random.default_rng(s)).generate()),
        ("Caliper-smallbank",      lambda s: CaliperBenchmark(
            mode="smallbank", n_tasks=500, tps=30,
            rng=np.random.default_rng(s)).generate()),
        ("Caliper-marbles02",      lambda s: CaliperBenchmark(
            mode="marbles02", n_tasks=500, tps=20,
            rng=np.random.default_rng(s)).generate()),
        ("TradeLens",              lambda s: TradeLensWorkload(
            days=1, docs_per_day=100,
            rng=np.random.default_rng(s)).generate()),
        ("MarcoPolo",              lambda s: MarcoPoloWorkload(
            hours=2, peak_hour=1.0, base_tps=0.5, peak_tps=5,
            rng=np.random.default_rng(s)).generate()),
        ("B3i",                    lambda s: B3iWorkload(
            n_tasks=500,
            rng=np.random.default_rng(s)).generate()),
        ("CBDC",                   lambda s: CBDCWorkload(
            n_windows=4, window_sec=300, txs_per_window=50,
            rng=np.random.default_rng(s)).generate()),
        ("Bursty",                 lambda s: BurstyWorkload(
            n_bursts=5, burst_size=50,
            rng=np.random.default_rng(s)).generate()),
    ]
    all_records = []
    for name, fac in factories:
        df = run_workload_eval(fac, name)
        all_records.append(df)

    big = pd.concat(all_records, ignore_index=True)
    out = Path(__file__).resolve().parent / "results" / "F5_workloads.csv"
    out.parent.mkdir(exist_ok=True)
    big.to_csv(out, index=False)

    # Aggregate per workload
    agg = big.groupby("workload").agg(
        n_tasks_mean=("n_tasks", "mean"),
        hc_miss_rate_mean=("hc_miss_rate", "mean"),
        lc_miss_rate_mean=("lc_miss_rate", "mean"),
        critical_frac_mean=("critical_fraction", "mean"),
    ).reset_index()
    print("\n=== F5 - Workload Evaluation Summary ===")
    print(agg.to_string(index=False))

    # CI for HC miss rate (most critical metric)
    print("\n=== HC miss rate 95% CI per workload ===")
    for name in big["workload"].unique():
        rates = big[big["workload"] == name]["hc_miss_rate"].values
        ci = bootstrap_ci(rates, np.mean, n_boot=2000)
        print(f"  {name:25s}: {ci}")
    print(f"\nSaved to {out}")
