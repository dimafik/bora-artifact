"""TX-1: Schedulability test scaling pilot + full.

RT-best-paper standard: M = 10^4 to 10^7 tasks.

Measures:
  - Wall-clock time vs M
  - Peak memory vs M
  - Empirical complexity slope (log-log linear regression)
  - Bonferroni adjustment behavior at large M
  - Decision rate (YES/NO) at various densities

Verifies Theorem 2's O(M log M) complexity claim empirically.
"""
from __future__ import annotations
import sys
import time
import gc
import tracemalloc
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd

from is_raft.schedulability import ConsensusTask, CPLForecast, lac_schedulability_test


def make_large_workload(M: int, density: float, rng) -> tuple:
    workload = []
    forecasts = {}
    total_time = M / max(density, 1e-6)
    arrivals = rng.uniform(0, total_time, size=M)
    wcets = rng.uniform(0.5, 1.5, size=M)
    deadline_extras = rng.uniform(1.0, 5.0, size=M)
    for i in range(M):
        task = ConsensusTask(
            task_id=f"T{i}",
            arrival_time=float(arrivals[i]),
            wcet=float(wcets[i]),
            deadline=float(arrivals[i] + wcets[i] + deadline_extras[i]),
            criticality="HC" if (i % 3 == 0) else "LC",
        )
        workload.append(task)
        forecasts[task.task_id] = CPLForecast(
            expected=float(wcets[i]) * 0.95,
            zeta=0.1, kappa=1.05,
        )
    return workload, forecasts


def run_scaling_pilot(M_values=(10_000, 50_000, 100_000),
                      densities=(0.1, 0.3, 0.5), seed: int = 0):
    records = []
    for M in M_values:
        for density in densities:
            gc.collect()
            tracemalloc.start()
            rng = np.random.default_rng(seed + M + int(density * 100))
            t0 = time.perf_counter()
            wl, fcs = make_large_workload(M, density, rng)
            t_build = time.perf_counter() - t0

            t0 = time.perf_counter()
            result = lac_schedulability_test(wl, fcs, N=11, delta=0.05)
            t_sched = time.perf_counter() - t0

            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()

            records.append({
                "M": M,
                "density": density,
                "decision": result.decision,
                "build_time_s": t_build,
                "sched_time_s": t_sched,
                "sched_time_ms": t_sched * 1000,
                "peak_memory_MB": peak / (1024**2),
            })
            print(f"M={M:>9d}, density={density:.2f}, decision={result.decision}, "
                  f"sched={t_sched*1000:.2f}ms, mem={peak/(1024**2):.1f}MB")
    df = pd.DataFrame(records)
    # Fit log-log slope on sched_time vs M
    for density in densities:
        sub = df[df["density"] == density]
        if len(sub) > 1:
            log_M = np.log(sub["M"].values)
            log_t = np.log(np.maximum(sub["sched_time_s"].values, 1e-9))
            slope = float(np.polyfit(log_M, log_t, 1)[0])
            print(f"  density={density}: complexity slope = {slope:.3f} (expected ~1.0 for M log M)")
    return df


def run_scaling_full(M_values=(10_000, 100_000, 1_000_000, 5_000_000),
                     density: float = 0.3, seed: int = 0):
    """Phase A Week 3: Full TX-1 to M=5M (1M+ as headline)."""
    records = []
    for M in M_values:
        gc.collect()
        tracemalloc.start()
        rng = np.random.default_rng(seed + M)
        t0 = time.perf_counter()
        wl, fcs = make_large_workload(M, density, rng)
        t_build = time.perf_counter() - t0
        print(f"  M={M:>9d} build done ({t_build:.1f}s)", flush=True)

        t0 = time.perf_counter()
        result = lac_schedulability_test(wl, fcs, N=11, delta=0.05)
        t_sched = time.perf_counter() - t0

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        records.append({
            "M": M,
            "density": density,
            "decision": result.decision,
            "build_time_s": t_build,
            "sched_time_s": t_sched,
            "sched_time_ms": t_sched * 1000,
            "peak_memory_MB": peak / (1024**2),
            "throughput_Mtasks_per_s": M / max(t_sched, 1e-9) / 1e6,
        })
        print(f"  M={M:>9d}, decision={result.decision}, "
              f"sched={t_sched*1000:.1f}ms, mem={peak/(1024**2):.1f}MB, "
              f"throughput={M/max(t_sched,1e-9)/1e6:.2f}M/s", flush=True)
    df = pd.DataFrame(records)
    log_M = np.log(df["M"].values)
    log_t = np.log(np.maximum(df["sched_time_s"].values, 1e-9))
    slope = float(np.polyfit(log_M, log_t, 1)[0])
    df.attrs["complexity_slope"] = slope
    return df


if __name__ == "__main__":
    out_dir = Path(__file__).resolve().parent / "results"
    out_dir.mkdir(exist_ok=True)
    import sys as _sys
    mode = _sys.argv[1] if len(_sys.argv) > 1 else "pilot"
    if mode == "pilot":
        print("\n=== TX-1 PILOT: M=10K-100K ===")
        df = run_scaling_pilot()
        df.to_csv(out_dir / "TX1_pilot.csv", index=False)
    elif mode == "full":
        print("\n=== TX-1 FULL: M=10K to 5M ===")
        df = run_scaling_full()
        df.to_csv(out_dir / "TX1_full.csv", index=False)
        print(f"\nEmpirical complexity slope: {df.attrs['complexity_slope']:.3f}")
        print(f"  (expected ~1.0 for O(M log M))")
    print("\nSaved to results/")
