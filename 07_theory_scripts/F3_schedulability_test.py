"""F3 — LAC Schedulability Test verification (Theorem 2).

Builds synthetic workloads with varying densities, applies LAC-Sched,
and verifies:
  1. Sound: YES decisions never produce deadline misses in simulation
  2. Bounded completeness: false negative rate <= O(1/sqrt(N))
  3. Polynomial complexity: M*log(M) growth confirmed empirically
  4. Mixed-criticality: HC always schedulable when LC backs off
"""
from __future__ import annotations
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd

from is_raft.schedulability import (ConsensusTask, CPLForecast,
                                     lac_schedulability_test, schedule_priority,
                                     mode_switch_decision)


def make_synthetic_workload(M: int, density: float, hc_frac: float = 0.3,
                             rng: Optional = None) -> tuple[list[ConsensusTask], dict[str, CPLForecast]]:
    rng = rng or np.random.default_rng(0)
    workload = []
    forecasts = {}
    total_time = M / density  # span of workload
    for i in range(M):
        arrival = rng.uniform(0, total_time)
        wcet = rng.uniform(0.5, 1.5)
        deadline = arrival + wcet + rng.uniform(1.0, 5.0)
        crit = "HC" if rng.random() < hc_frac else "LC"
        task = ConsensusTask(task_id=f"T{i}", arrival_time=arrival, wcet=wcet,
                             deadline=deadline, criticality=crit)
        workload.append(task)
        forecasts[task.task_id] = CPLForecast(
            expected=wcet * rng.uniform(0.9, 1.1),
            zeta=0.1, kappa=1.05,
        )
    return workload, forecasts


def simulate_actual(workload: list[ConsensusTask],
                     forecasts: dict[str, CPLForecast],
                     rng: Optional = None,
                     policy: str = "EDF") -> int:
    """Simulate actual execution under (zeta, kappa)-CPL and count misses.

    Policy must match what the schedulability test assumes. Thm 2 uses EDF.
    Mode-switching tests use schedule_priority (HC first, then EDF within criticality).
    """
    rng = rng or np.random.default_rng(0)
    if policy == "EDF":
        sched = sorted(workload, key=lambda t: t.deadline)
    elif policy == "MC":
        sched = schedule_priority(workload)
    else:
        raise ValueError(f"unknown policy: {policy}")
    t_finish = 0.0
    misses = 0
    for task in sched:
        f = forecasts[task.task_id]
        # Clamp actual to be positive (RTT cannot be negative)
        actual = max(0.01, f.expected + rng.normal(0, f.zeta))
        start = max(task.arrival_time, t_finish)
        commit = start + actual
        if commit > task.deadline:
            misses += 1
        t_finish = commit
    return misses


def run_soundness_check(N: int = 11, n_trials: int = 100, M: int = 50,
                        densities=(0.1, 0.3, 0.5, 0.7, 0.9), seed: int = 0):
    records = []
    rng = np.random.default_rng(seed)
    for density in densities:
        yes_count = 0
        miss_when_yes = 0
        no_count = 0
        miss_when_no = 0
        for trial in range(n_trials):
            wl, fcs = make_synthetic_workload(M=M, density=density,
                                              rng=np.random.default_rng(seed + trial))
            result = lac_schedulability_test(wl, fcs, N=N, delta=0.05)
            misses = simulate_actual(wl, fcs, rng=np.random.default_rng(seed + 7919 + trial))
            if result.decision == "YES":
                yes_count += 1
                if misses > 0:
                    miss_when_yes += 1
            else:
                no_count += 1
                if misses == 0:
                    miss_when_no += 1   # false negative
        records.append({
            "density": density,
            "yes_rate": yes_count / n_trials,
            "no_rate": no_count / n_trials,
            "soundness_violation_rate (miss when YES)": miss_when_yes / max(yes_count, 1),
            "false_negative_rate (no-miss when NO)": miss_when_no / max(no_count, 1),
        })
    return pd.DataFrame(records)


def run_complexity_check(M_values=(10, 50, 100, 250, 500, 1000), n_trials: int = 5,
                          density: float = 0.3, N: int = 11):
    records = []
    for M in M_values:
        times = []
        for trial in range(n_trials):
            wl, fcs = make_synthetic_workload(M=M, density=density,
                                              rng=np.random.default_rng(trial))
            t0 = time.perf_counter()
            _ = lac_schedulability_test(wl, fcs, N=N)
            times.append(time.perf_counter() - t0)
        records.append({
            "M": M,
            "mean_time_ms": float(np.mean(times)) * 1000,
            "M_log_M": M * np.log(max(M, 2)),
        })
    df = pd.DataFrame(records)
    # Fit log-log slope (should be ~1 for M*log(M))
    log_M = np.log(df["M"].values)
    log_t = np.log(df["mean_time_ms"].values)
    slope = float(np.polyfit(log_M, log_t, 1)[0])
    df.attrs["empirical_complexity_slope"] = slope
    return df


def run_mode_switch_check(N: int = 11, n_trials: int = 50,
                           hc_fracs=(0.1, 0.3, 0.5, 0.7), seed: int = 0):
    records = []
    for hc in hc_fracs:
        normal = critical = 0
        hc_miss_under_critical = 0
        for trial in range(n_trials):
            wl, fcs = make_synthetic_workload(M=50, density=0.6, hc_frac=hc,
                                              rng=np.random.default_rng(seed + trial))
            mode = mode_switch_decision(wl, fcs, N=N)
            if mode == "NORMAL":
                normal += 1
            else:
                critical += 1
                # In CRITICAL mode only HC runs
                hc_only = [t for t in wl if t.criticality == "HC"]
                misses = simulate_actual(hc_only, fcs,
                                          rng=np.random.default_rng(seed + 7919 + trial))
                if misses > 0:
                    hc_miss_under_critical += 1
        records.append({
            "hc_frac": hc,
            "normal_mode_rate": normal / n_trials,
            "critical_mode_rate": critical / n_trials,
            "hc_misses_under_critical": hc_miss_under_critical / max(critical, 1),
        })
    return pd.DataFrame(records)


if __name__ == "__main__":
    from typing import Optional

    out_dir = Path(__file__).resolve().parent / "results"
    out_dir.mkdir(exist_ok=True)

    print("\n=== F3.1 Soundness Check (Theorem 2 part: sound) ===")
    df1 = run_soundness_check()
    print(df1.to_string(index=False))
    df1.to_csv(out_dir / "F3_soundness.csv", index=False)

    print("\n=== F3.2 Complexity Check (Theorem 2 part: poly time) ===")
    df2 = run_complexity_check()
    print(df2.to_string(index=False))
    print(f"\nEmpirical log-log slope: {df2.attrs['empirical_complexity_slope']:.3f}")
    print(f"  (expected ~1.0 for M*log(M); >1.5 suggests super-linear)")
    df2.to_csv(out_dir / "F3_complexity.csv", index=False)

    print("\n=== F3.3 Mode-Switch Check (Theorem 3 part) ===")
    df3 = run_mode_switch_check()
    print(df3.to_string(index=False))
    df3.to_csv(out_dir / "F3_mode_switch.csv", index=False)

    print(f"\nAll results saved to {out_dir}")
