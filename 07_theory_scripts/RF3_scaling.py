"""RF-3: 1000-node scaling experiment.

Scales committee size N from 11 to 1000 (Mysticeti-class scale).
Measures:
  - Per-round scheduler latency
  - Per-round oracle inference time
  - Memory usage
  - Throughput-latency curve
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

from is_raft.oracle import MockOracle, OracleInput
from is_raft.protocol import ISRaftProtocol


def make_committee_workload(N: int, n_rounds: int = 200, rng=None) -> list:
    """Generate RTT vectors for a committee of size N over n_rounds."""
    rng = rng or np.random.default_rng(0)
    return [rng.exponential(1.0, size=N) for _ in range(n_rounds)]


def run_rf3(N_values=(11, 21, 50, 100, 250, 500, 1000),
            n_rounds: int = 100, k_frac: float = 0.3, seed: int = 0):
    print("\n=== RF-3: 1000-node scaling ===\n")
    records = []
    for N in N_values:
        gc.collect()
        tracemalloc.start()
        rng = np.random.default_rng(seed + N)
        k = max(3, int(N * k_frac))
        oracle = MockOracle(window=50)
        is_raft = ISRaftProtocol(oracle, N=N, k=k, delta_max=float("inf"))

        samples = make_committee_workload(N, n_rounds, rng)
        history = []

        # Time per-round operations
        oracle_times = []
        scheduler_times = []
        for r_t in samples:
            H = np.array(history[-100:]) if history else np.zeros((0, N))
            inp = OracleInput(rtt_history=H, vote_delays=np.zeros_like(H),
                              promote_outcomes=np.zeros_like(H), round_idx=len(history))
            t0 = time.perf_counter_ns()
            out = is_raft.run_round(r_t, inp)
            scheduler_times.append((time.perf_counter_ns() - t0) / 1000)  # μs
            history.append(r_t)

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        records.append({
            "N": N,
            "k": k,
            "n_rounds": n_rounds,
            "scheduler_mean_us": float(np.mean(scheduler_times)),
            "scheduler_p99_us": float(np.percentile(scheduler_times, 99)),
            "memory_MB": peak / (1024**2),
            "rounds_per_second": n_rounds / (sum(scheduler_times) / 1e6) if sum(scheduler_times) > 0 else 0,
        })
        print(f"  N={N:>5d}, k={k:>4d}: scheduler={np.mean(scheduler_times):.1f}us mean, "
              f"p99={np.percentile(scheduler_times, 99):.1f}us, "
              f"mem={peak/(1024**2):.1f}MB, "
              f"throughput={records[-1]['rounds_per_second']:.0f} rounds/s", flush=True)

    df = pd.DataFrame(records)
    out_dir = Path(__file__).resolve().parent / "results"
    out_dir.mkdir(exist_ok=True)
    df.to_csv(out_dir / "RF3_scaling.csv", index=False)

    # Complexity fit
    log_N = np.log(df["N"].values)
    log_t = np.log(df["scheduler_mean_us"].values)
    slope = float(np.polyfit(log_N, log_t, 1)[0])
    print(f"\nEmpirical scheduler complexity slope: {slope:.3f}")
    print(f"  (expected ~1.0 for O(N) per-round; higher = poor scaling)")
    return df


if __name__ == "__main__":
    run_rf3()
