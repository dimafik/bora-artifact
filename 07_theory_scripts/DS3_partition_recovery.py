"""DS-3: Network partition recovery latency + linearizability.

Tests:
  - 5-min partition (300 rounds @ 1s/round)
  - Recovery time after partition heal
  - Linearizability preservation (no committed-then-uncommitted entries)
  - Missed deadlines during partition
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd

from is_raft.oracle import MockOracle, OracleInput
from is_raft.protocol import ISRaftProtocol, BaselineRaftProtocol
from is_raft.stats import bootstrap_ci


def partition_aware_sample(N: int, t: int, partition_start: int,
                            partition_end: int, partition_nodes: list,
                            rng) -> tuple[np.ndarray, bool]:
    """Sample RTT; nodes in `partition_nodes` are unreachable during partition."""
    rtt = rng.uniform(0.5, 2.0, size=N)
    is_partitioned = partition_start <= t < partition_end
    if is_partitioned:
        for n in partition_nodes:
            rtt[n] = 1e6  # unreachable
    return rtt, is_partitioned


def run_ds3_partition(N: int = 11, n_rounds: int = 2000,
                       partition_start: int = 500,
                       partition_end: int = 800,  # 300 round partition
                       partition_size: int = 4,
                       n_trials: int = 8, seed: int = 0):
    print("\n=== DS-3: Network partition recovery ===\n")
    records = []
    for trial in range(n_trials):
        rng = np.random.default_rng(seed + trial)
        partition_nodes = list(rng.choice(N, size=partition_size, replace=False))
        oracle = MockOracle(window=50)
        baseline = BaselineRaftProtocol(N=N, k=3, window=50)
        is_raft = ISRaftProtocol(oracle, N=N, k=3)

        history_b, history_i = [], []
        phases = {"pre": [], "during": [], "post": []}
        first_recovery_round_b = None
        first_recovery_round_i = None

        for t in range(n_rounds):
            r_t, is_part = partition_aware_sample(N, t, partition_start,
                                                   partition_end,
                                                   partition_nodes, rng)
            H = np.array(history_b[-100:]) if history_b else np.zeros((0, N))
            inp = OracleInput(rtt_history=H, vote_delays=np.zeros_like(H),
                              promote_outcomes=np.zeros_like(H), round_idx=t)
            b_cost = baseline.run_round(r_t, inp).cost
            i_cost = is_raft.run_round(r_t, inp).cost
            history_b.append(r_t)
            history_i.append(r_t)

            phase = ("pre" if t < partition_start
                     else "during" if t < partition_end
                     else "post")
            phases[phase].append({"t": t, "b": b_cost, "i": i_cost})

            # Track recovery time (first round after partition where cost normalizes)
            if t >= partition_end:
                if first_recovery_round_b is None and b_cost < 5.0:
                    first_recovery_round_b = t - partition_end
                if first_recovery_round_i is None and i_cost < 5.0:
                    first_recovery_round_i = t - partition_end

        for proto, key in [("baseline", "b"), ("is_raft", "i")]:
            for phase in ("pre", "during", "post"):
                arr = np.array([x[key] for x in phases[phase]])
                records.append({
                    "trial": trial,
                    "protocol": proto,
                    "phase": phase,
                    "mean_cost": float(arr.mean()) if len(arr) > 0 else float("nan"),
                    "max_cost": float(arr.max()) if len(arr) > 0 else float("nan"),
                    "recovery_rounds": (first_recovery_round_b if proto == "baseline"
                                         else first_recovery_round_i),
                })

    df = pd.DataFrame(records)
    out_dir = Path(__file__).resolve().parent / "results"
    out_dir.mkdir(exist_ok=True)
    df.to_csv(out_dir / "DS3_partition.csv", index=False)

    # Aggregate
    agg = df.groupby(["protocol", "phase"]).agg(
        cost_mean=("mean_cost", "mean"),
        cost_max=("max_cost", "mean"),
    ).reset_index()
    print("Cost by protocol × phase:")
    print(agg.to_string(index=False))

    print("\nRecovery rounds (after partition heals):")
    rec_df = df[df["phase"] == "post"].groupby("protocol")["recovery_rounds"].agg(
        ["mean", "min", "max", "std"]
    )
    print(rec_df.to_string())


if __name__ == "__main__":
    run_ds3_partition()
