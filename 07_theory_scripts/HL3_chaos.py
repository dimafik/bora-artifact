"""HL-3: Chaos engineering — 5 failure injections.

Tests IS-Raft-MC recovery under:
  1. Network partition (entire AZ down)
  2. Slow node (10x RTT inflation)
  3. Leader crash
  4. Clock skew
  5. Message loss spike
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd

from is_raft.distributions import AdversarialNonStationary
from is_raft.oracle import MockOracle, OracleInput
from is_raft.protocol import ISRaftProtocol, BaselineRaftProtocol
from is_raft.stats import bootstrap_ci


def inject_chaos(r_t: np.ndarray, t: int, injection: str,
                  inject_round: int, recovery_round: int,
                  rng) -> np.ndarray:
    """Apply chaos injection to RTT vector."""
    r = r_t.copy()
    in_injection = inject_round <= t < recovery_round
    if not in_injection:
        return r

    N = len(r)
    if injection == "partition":
        # Take down nodes 7-10 (a "region")
        partition_set = list(range(min(7, N), N))
        r[partition_set] = 1e6
    elif injection == "slow_node":
        # 3 nodes become 10x slower
        slow_set = [0, 5, 10]
        for i in slow_set:
            if i < N:
                r[i] *= 10.0
    elif injection == "leader_crash":
        # Leader's primary backup (node 1) crashes
        r[1] = 1e6
    elif injection == "clock_skew":
        # All nodes' RTTs perturbed by ±50% (clock-related variance)
        skew = rng.uniform(0.5, 1.5, size=N)
        r = r * skew
    elif injection == "message_loss":
        # 30% of nodes randomly experience loss this round
        loss_mask = rng.random(N) < 0.3
        r[loss_mask] *= 3.0  # retransmission delay
    return np.maximum(0.001, r)


def run_chaos_study(n_rounds: int = 1000, inject_at: int = 300,
                    recovery_at: int = 600, seed: int = 0):
    print("\n=== HL-3: Chaos engineering injections ===\n")
    injections = ["partition", "slow_node", "leader_crash",
                  "clock_skew", "message_loss"]
    records = []
    for inj in injections:
        for seed_offset in range(5):
            rng = np.random.default_rng(seed + seed_offset)
            dist = AdversarialNonStationary(N=11, fast_rate=1.0, slow_rate=10.0,
                                            shift_mean=10,
                                            baseline_window_assumed=50, rng=rng)
            oracle = MockOracle(window=50)
            baseline = BaselineRaftProtocol(N=11, k=3, window=50)
            is_raft = ISRaftProtocol(oracle, N=11, k=3)

            sample_cache = [dist.sample(t) for t in range(n_rounds)]

            # Apply chaos to cache
            chaos_cache = [inject_chaos(r, t, inj, inject_at, recovery_at, rng)
                           for t, r in enumerate(sample_cache)]
            history_b, history_i = [], []
            costs = {"baseline": {"pre": [], "during": [], "post": []},
                     "is_raft":  {"pre": [], "during": [], "post": []}}
            for t in range(n_rounds):
                r_t = chaos_cache[t]
                phase = "pre" if t < inject_at else ("during" if t < recovery_at else "post")
                H = np.array(history_b[-100:]) if history_b else np.zeros((0, 11))
                inp = OracleInput(rtt_history=H, vote_delays=np.zeros_like(H),
                                  promote_outcomes=np.zeros_like(H), round_idx=t)
                costs["baseline"][phase].append(baseline.run_round(r_t, inp).cost)
                history_b.append(r_t)
                H_i = np.array(history_i[-100:]) if history_i else np.zeros((0, 11))
                inp_i = OracleInput(rtt_history=H_i, vote_delays=np.zeros_like(H_i),
                                    promote_outcomes=np.zeros_like(H_i), round_idx=t)
                costs["is_raft"][phase].append(is_raft.run_round(r_t, inp_i).cost)
                history_i.append(r_t)

            for proto in ("baseline", "is_raft"):
                for phase in ("pre", "during", "post"):
                    arr = np.array(costs[proto][phase])
                    records.append({
                        "injection": inj,
                        "seed": seed_offset,
                        "protocol": proto,
                        "phase": phase,
                        "mean_cost": float(arr.mean()) if len(arr) > 0 else float("nan"),
                        "p99_cost": float(np.percentile(arr, 99)) if len(arr) > 0 else float("nan"),
                    })
    df = pd.DataFrame(records)
    out_dir = Path(__file__).resolve().parent / "results"
    out_dir.mkdir(exist_ok=True)
    df.to_csv(out_dir / "HL3_chaos.csv", index=False)

    # Aggregate
    agg = df.groupby(["injection", "protocol", "phase"]).agg(
        cost_mean=("mean_cost", "mean"),
        cost_p99=("p99_cost", "mean"),
    ).reset_index()
    print("Injection × protocol × phase summary:")
    pvt = agg.pivot_table(index=["injection", "phase"],
                           columns="protocol", values="cost_mean")
    pvt["recovery_factor"] = pvt["baseline"] / pvt["is_raft"]
    print(pvt.to_string())
    return df


if __name__ == "__main__":
    run_chaos_study()
