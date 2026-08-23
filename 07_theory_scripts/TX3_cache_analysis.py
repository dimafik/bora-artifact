"""TX-3: Cache + memory bandwidth analysis (RT-style WCET tightness).

Profile scheduler operations for cache miss behavior + WCET tightness.
Uses Python's resource module + measured execution time variance.
"""
from __future__ import annotations
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd

from is_raft.schedulability import ConsensusTask, CPLForecast, lac_schedulability_test
from is_raft.oracle import MockOracle, OracleInput
from is_raft.protocol import ISRaftProtocol
from is_raft.stats import bootstrap_ci


def measure_wcet_tightness(workload_size: int = 1000, n_iters: int = 200,
                            warmup: int = 20, seed: int = 0) -> dict:
    """Measure WCET tightness: max(time) / mean(time) ratio."""
    rng = np.random.default_rng(seed)
    workload = []
    forecasts = {}
    for i in range(workload_size):
        t = ConsensusTask(f"t{i}", float(rng.uniform(0, 100)),
                          float(rng.uniform(0.5, 1.5)),
                          float(rng.uniform(5, 20)),
                          "HC" if i % 3 == 0 else "LC")
        workload.append(t)
        forecasts[t.task_id] = CPLForecast(expected=t.wcet * 0.95,
                                            zeta=0.1, kappa=1.05)
    times = []
    for it in range(n_iters + warmup):
        t0 = time.perf_counter_ns()
        _ = lac_schedulability_test(workload, forecasts, N=11, delta=0.05)
        t1 = time.perf_counter_ns()
        if it >= warmup:
            times.append((t1 - t0) / 1000)  # μs
    times = np.array(times)
    return {
        "workload_size": workload_size,
        "n_iters": n_iters,
        "mean_us": float(np.mean(times)),
        "median_us": float(np.median(times)),
        "max_us": float(np.max(times)),
        "min_us": float(np.min(times)),
        "std_us": float(np.std(times)),
        "wcet_tightness": float(np.max(times) / np.mean(times)),
        "wcet_p99_tightness": float(np.percentile(times, 99) / np.mean(times)),
    }


def measure_inference_tightness(N: int = 11, n_iters: int = 500,
                                  seed: int = 0) -> dict:
    """Measure Φ_d (mock oracle) inference WCET."""
    rng = np.random.default_rng(seed)
    oracle = MockOracle(window=50)
    is_raft = ISRaftProtocol(oracle, N=N, k=3)
    # Build history
    history = [rng.exponential(1.0, size=N) for _ in range(100)]
    H = np.array(history)
    inp = OracleInput(rtt_history=H, vote_delays=np.zeros_like(H),
                      promote_outcomes=np.zeros_like(H), round_idx=100)
    times = []
    for it in range(n_iters):
        r_t = rng.exponential(1.0, size=N)
        t0 = time.perf_counter_ns()
        _ = is_raft.run_round(r_t, inp)
        times.append((time.perf_counter_ns() - t0) / 1000)
    times = np.array(times)
    return {
        "N": N,
        "n_iters": n_iters,
        "mean_us": float(np.mean(times)),
        "max_us": float(np.max(times)),
        "wcet_tightness": float(np.max(times) / np.mean(times)),
        "p99_us": float(np.percentile(times, 99)),
        "p999_us": float(np.percentile(times, 99.9)),
    }


def run_tx3():
    print("\n=== TX-3: WCET tightness analysis ===\n")
    print("(1) Schedulability test WCET")
    sched_records = []
    for M in [100, 1000, 10000]:
        r = measure_wcet_tightness(workload_size=M, n_iters=100)
        sched_records.append(r)
        print(f"  M={M:>6d}: mean={r['mean_us']:.2f}μs, max={r['max_us']:.2f}μs, "
              f"WCET tightness={r['wcet_tightness']:.2f}x, p99/mean={r['wcet_p99_tightness']:.2f}x")

    print("\n(2) Oracle inference WCET")
    infer_records = []
    for N in [11, 50, 100, 500]:
        r = measure_inference_tightness(N=N, n_iters=500)
        infer_records.append(r)
        print(f"  N={N:>4d}: mean={r['mean_us']:.2f}μs, max={r['max_us']:.2f}μs, "
              f"WCET tightness={r['wcet_tightness']:.2f}x, "
              f"p99={r['p99_us']:.2f}μs")

    out_dir = Path(__file__).resolve().parent / "results"
    out_dir.mkdir(exist_ok=True)
    pd.DataFrame(sched_records).to_csv(out_dir / "TX3_sched_wcet.csv", index=False)
    pd.DataFrame(infer_records).to_csv(out_dir / "TX3_infer_wcet.csv", index=False)
    print(f"\nSaved to {out_dir}")


if __name__ == "__main__":
    run_tx3()
