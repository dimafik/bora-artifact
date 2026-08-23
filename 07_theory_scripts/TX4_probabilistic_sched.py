"""TX-4: Probabilistic Schedulability Analysis (Maxim-style pSCA).

Instead of point estimates of WCET, model task execution times as full
distributions. Schedulability becomes a probability distribution.

Per Maxim 2017 framework, this is the appropriate model for systems
with uncertain timing — exactly our scenario where (zeta, kappa)-CPL
introduces uncertainty.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd

from is_raft.schedulability import (ConsensusTask, CPLForecast,
                                     lac_schedulability_test)
from is_raft.stats import bootstrap_ci


def probabilistic_sched_test(workload: list, forecasts: dict,
                               N: int = 11, delta: float = 0.05,
                               n_samples: int = 1000, seed: int = 0) -> dict:
    """Monte Carlo evaluation of schedulability probability.

    For each MC sample:
      1. Sample actual execution times from CPL distribution
      2. Simulate execution
      3. Record if any deadline missed

    Returns the probability of full schedulability + per-task miss probability.
    """
    rng = np.random.default_rng(seed)
    sched_ordered = sorted(workload, key=lambda t: t.deadline)
    n_misses_per_run = []
    task_miss_count = {t.task_id: 0 for t in workload}

    for run in range(n_samples):
        t_finish = 0.0
        run_misses = 0
        for task in sched_ordered:
            f = forecasts[task.task_id]
            actual = max(0.001, f.expected + rng.normal(0, f.zeta))
            start = max(task.arrival_time, t_finish)
            commit = start + actual
            if commit > task.deadline:
                run_misses += 1
                task_miss_count[task.task_id] += 1
            t_finish = commit
        n_misses_per_run.append(run_misses)

    n_misses_arr = np.array(n_misses_per_run)
    schedulable_prob = float(np.mean(n_misses_arr == 0))
    expected_misses = float(np.mean(n_misses_arr))
    max_misses = int(np.max(n_misses_arr))

    # Per-task miss probability
    task_miss_probs = {tid: cnt / n_samples for tid, cnt in task_miss_count.items()}
    max_task_miss_prob = max(task_miss_probs.values()) if task_miss_probs else 0.0

    return {
        "n_samples": n_samples,
        "schedulable_prob": schedulable_prob,
        "expected_misses_per_run": expected_misses,
        "max_misses_per_run": max_misses,
        "max_task_miss_prob": max_task_miss_prob,
        "task_miss_probs": task_miss_probs,
    }


def run_tx4():
    print("\n=== TX-4: Probabilistic Schedulability Analysis ===\n")
    records = []
    rng = np.random.default_rng(0)

    for n_tasks in [10, 50, 100]:
        for utilization in [0.3, 0.5, 0.7, 0.9]:
            # Build workload at target utilization
            workload = []
            forecasts = {}
            total_time = n_tasks / utilization
            for i in range(n_tasks):
                arrival = rng.uniform(0, total_time)
                wcet = rng.uniform(0.5, 1.5)
                deadline = arrival + wcet + rng.uniform(1.0, 3.0)
                t = ConsensusTask(f"t{i}", arrival, wcet, deadline,
                                   "HC" if i % 3 == 0 else "LC")
                workload.append(t)
                forecasts[t.task_id] = CPLForecast(expected=wcet * 0.95,
                                                    zeta=0.1, kappa=1.05)

            # Deterministic schedulability test
            det_result = lac_schedulability_test(workload, forecasts, N=11, delta=0.05)
            # Probabilistic
            prob_result = probabilistic_sched_test(workload, forecasts,
                                                     n_samples=500, seed=int(utilization * 1000) + n_tasks)

            records.append({
                "n_tasks": n_tasks,
                "utilization": utilization,
                "det_decision": det_result.decision,
                "prob_schedulable": prob_result["schedulable_prob"],
                "expected_misses": prob_result["expected_misses_per_run"],
                "max_task_miss_prob": prob_result["max_task_miss_prob"],
            })

    df = pd.DataFrame(records)
    out_dir = Path(__file__).resolve().parent / "results"
    out_dir.mkdir(exist_ok=True)
    df.to_csv(out_dir / "TX4_pSCA.csv", index=False)

    print("Probabilistic vs deterministic schedulability:")
    print(df.to_string(index=False))

    # Comparison: when det=NO, what's prob_schedulable?
    print("\nDet=NO cases — probabilistic schedulability:")
    no_cases = df[df["det_decision"] == "NO"]
    print(no_cases[["n_tasks", "utilization", "prob_schedulable", "expected_misses"]].to_string(index=False))
    print(f"\n(Det=NO might still have high prob_schedulable, showing test conservatism)")


if __name__ == "__main__":
    run_tx4()
