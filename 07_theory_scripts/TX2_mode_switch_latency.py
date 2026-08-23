"""TX-2: Mode-switching transition latency measurement.

Measures the latency from CRITICAL-mode trigger to first HC commit
under suspended LC tasks. RT-best-paper standard: distribution analysis
(mean, p99, p99.9) over many transitions.

Compares with classical EDF (no mode switching) and a naive priority
scheduler.
"""
from __future__ import annotations
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd

from is_raft.schedulability import (ConsensusTask, CPLForecast, mode_switch_decision,
                                     schedule_priority)
from is_raft.stats import bootstrap_ci


def make_burst_workload(n_lc_pre: int, n_hc_burst: int, n_lc_post: int,
                         lc_arrival_rate: float, hc_burst_at: float,
                         rng) -> tuple[list, dict]:
    """Workload: LC steady stream, then HC burst, then LC continues."""
    workload, forecasts = [], {}
    # LC pre-burst (low arrival rate)
    for i in range(n_lc_pre):
        a = rng.exponential(1.0 / lc_arrival_rate) * i / n_lc_pre * hc_burst_at
        wcet = max(0.1, rng.normal(0.3, 0.05))
        deadline = a + wcet + rng.uniform(2.0, 5.0)
        task = ConsensusTask(f"LC_pre_{i}", a, wcet, deadline, "LC")
        workload.append(task)
        forecasts[task.task_id] = CPLForecast(expected=wcet * 0.95, zeta=0.05, kappa=1.05)
    # HC burst
    for i in range(n_hc_burst):
        a = hc_burst_at + rng.uniform(0, 0.5)
        wcet = max(0.1, rng.normal(0.4, 0.08))
        deadline = a + wcet + rng.uniform(0.5, 1.5)  # tight deadlines
        task = ConsensusTask(f"HC_burst_{i}", a, wcet, deadline, "HC")
        workload.append(task)
        forecasts[task.task_id] = CPLForecast(expected=wcet * 0.95, zeta=0.04, kappa=1.05)
    # LC post-burst
    base = hc_burst_at + 5.0
    for i in range(n_lc_post):
        a = base + rng.exponential(1.0 / lc_arrival_rate) * i
        wcet = max(0.1, rng.normal(0.3, 0.05))
        deadline = a + wcet + rng.uniform(2.0, 5.0)
        task = ConsensusTask(f"LC_post_{i}", a, wcet, deadline, "LC")
        workload.append(task)
        forecasts[task.task_id] = CPLForecast(expected=wcet * 0.95, zeta=0.05, kappa=1.05)
    return workload, forecasts


def simulate_with_mode_tracking(workload, forecasts, rng,
                                  scheduler_mode: str = "MC") -> dict:
    """Simulate execution with detailed mode-transition tracking.

    scheduler_mode:
      - "MC": IS-Raft-MC with mode switching
      - "EDF": pure EDF, no priority
      - "FIFO": first-come-first-served
    """
    if scheduler_mode == "MC":
        sched = schedule_priority(workload)
    elif scheduler_mode == "EDF":
        sched = sorted(workload, key=lambda t: t.deadline)
    elif scheduler_mode == "FIFO":
        sched = sorted(workload, key=lambda t: t.arrival_time)
    else:
        raise ValueError(scheduler_mode)

    t_finish = 0.0
    transitions = []  # (trigger_time, first_hc_commit_time) per transition
    current_mode = "NORMAL"
    mode_critical_start = None
    first_hc_after_critical = None
    misses = {"HC": 0, "LC": 0}

    for ti, task in enumerate(sched):
        # MC mode logic
        if scheduler_mode == "MC":
            remaining_at_t = [t for t in workload
                              if t.arrival_time >= task.arrival_time]
            mode = mode_switch_decision(remaining_at_t[:30], forecasts, N=11,
                                        slack_guard=0.5)
            if mode == "CRITICAL" and current_mode == "NORMAL":
                mode_critical_start = max(task.arrival_time, t_finish)
                first_hc_after_critical = None
            elif mode == "NORMAL" and current_mode == "CRITICAL":
                # Mode returned to NORMAL
                pass
            current_mode = mode
            if mode == "CRITICAL" and task.criticality == "LC":
                continue  # suspend LC

        f = forecasts[task.task_id]
        actual = max(0.001, f.expected + rng.normal(0, f.zeta))
        start = max(task.arrival_time, t_finish)
        commit = start + actual

        # Mode transition tracking
        if (mode_critical_start is not None and
            first_hc_after_critical is None and
            task.criticality == "HC"):
            transition_latency = commit - mode_critical_start
            transitions.append({
                "trigger_time": mode_critical_start,
                "first_hc_commit": commit,
                "latency_ms": transition_latency * 1000,
            })
            first_hc_after_critical = commit
            mode_critical_start = None

        if commit > task.deadline:
            misses[task.criticality] += 1
        t_finish = commit

    return {
        "scheduler": scheduler_mode,
        "n_transitions": len(transitions),
        "transitions": transitions,
        "hc_miss": misses["HC"],
        "lc_miss": misses["LC"],
    }


def run_pilot(n_trials: int = 10, seed: int = 0):
    print("\n=== TX-2 PILOT ===\n")
    all_transitions = {"MC": [], "EDF": [], "FIFO": []}
    miss_records = []
    for trial in range(n_trials):
        rng = np.random.default_rng(seed + trial)
        wl, fcs = make_burst_workload(
            n_lc_pre=20, n_hc_burst=15, n_lc_post=20,
            lc_arrival_rate=0.5, hc_burst_at=5.0, rng=rng,
        )
        for mode in ("MC", "EDF", "FIFO"):
            sim_rng = np.random.default_rng(seed + trial * 7919)
            res = simulate_with_mode_tracking(wl, fcs, sim_rng, mode)
            for tr in res["transitions"]:
                all_transitions[mode].append(tr["latency_ms"])
            miss_records.append({
                "trial": trial, "scheduler": mode,
                "n_transitions": res["n_transitions"],
                "hc_miss": res["hc_miss"], "lc_miss": res["lc_miss"],
            })

    out_dir = Path(__file__).resolve().parent / "results"
    out_dir.mkdir(exist_ok=True)
    miss_df = pd.DataFrame(miss_records)
    miss_df.to_csv(out_dir / "TX2_pilot_misses.csv", index=False)

    print("Mode-switch transition latency (only MC has transitions):")
    for mode, lats in all_transitions.items():
        if lats:
            arr = np.array(lats)
            ci = bootstrap_ci(arr, np.mean, n_boot=2000)
            print(f"  {mode:5s}: n={len(arr):>3d}, mean={arr.mean():.2f}ms, "
                  f"p50={np.percentile(arr,50):.2f}ms, p99={np.percentile(arr,99):.2f}ms, "
                  f"95CI={ci}")
        else:
            print(f"  {mode:5s}: no transitions (expected for non-MC)")

    print("\nMiss rates by scheduler:")
    agg = miss_df.groupby("scheduler").agg(
        hc_miss_mean=("hc_miss", "mean"),
        lc_miss_mean=("lc_miss", "mean"),
        n_trans_mean=("n_transitions", "mean"),
    )
    print(agg)

    # Save transition data
    flat_rows = []
    for mode, lats in all_transitions.items():
        for l in lats:
            flat_rows.append({"scheduler": mode, "latency_ms": l})
    pd.DataFrame(flat_rows).to_csv(out_dir / "TX2_pilot_transitions.csv", index=False)


if __name__ == "__main__":
    run_pilot()
