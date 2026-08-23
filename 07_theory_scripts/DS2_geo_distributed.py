"""DS-2: Geo-distributed multi-cloud deployment simulation.

Realistic cross-region RTT matrix for AWS US-East + GCP EU + Azure APAC:
  - Intra-region: ~1-5ms
  - US-East <-> EU: ~80ms
  - US-East <-> APAC: ~180ms
  - EU <-> APAC: ~250ms

Measures schedulability degradation under geo-distributed deployment.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd

from is_raft.oracle import MockOracle, OracleInput
from is_raft.protocol import ISRaftProtocol, BaselineRaftProtocol
from is_raft.stats import bootstrap_ci, paired_test


class GeoDistributedNetwork:
    """Simulates RTT in a 3-region 9-node deployment.
    Nodes 0-2: AWS US-East
    Nodes 3-5: GCP EU-West
    Nodes 6-8: Azure APAC
    """
    REGION_MAP = {
        "us_east": [0, 1, 2],
        "eu_west": [3, 4, 5],
        "apac":    [6, 7, 8],
    }

    BASE_RTT = {
        ("us_east", "us_east"): 2.0,
        ("eu_west", "eu_west"): 3.0,
        ("apac", "apac"):       4.0,
        ("us_east", "eu_west"): 80.0,
        ("us_east", "apac"):    180.0,
        ("eu_west", "apac"):    250.0,
    }

    def __init__(self, N: int = 9, jitter_scale: float = 0.1,
                 congestion_probability: float = 0.05,
                 rng=None):
        assert N == 9, "DS-2 fixed N=9"
        self.N = N
        self.jitter_scale = jitter_scale
        self.congestion_probability = congestion_probability
        self.rng = rng or np.random.default_rng(0)
        # Pre-build region per node
        self.node_region = {}
        for region, nodes in self.REGION_MAP.items():
            for n in nodes:
                self.node_region[n] = region
        # Build base RTT matrix
        self.base_rtt_matrix = np.zeros((N, N))
        for i in range(N):
            for j in range(N):
                if i == j:
                    continue
                r1, r2 = self.node_region[i], self.node_region[j]
                key = (r1, r2) if (r1, r2) in self.BASE_RTT else (r2, r1)
                self.base_rtt_matrix[i, j] = self.BASE_RTT[key]

    def sample(self, t: int) -> np.ndarray:
        """RTT vector from leader (node 0, us_east) to all OTHER nodes.
        Self-RTT replaced with large sentinel to prevent self-selection."""
        leader = 0
        rtts = self.base_rtt_matrix[leader].copy()
        jitter = self.rng.normal(0, self.jitter_scale * np.maximum(rtts, 1.0), size=self.N)
        rtts = np.maximum(0.1, rtts + jitter)
        congested = self.rng.random(self.N) < self.congestion_probability
        if congested.any():
            rtts[congested] *= self.rng.uniform(2.0, 5.0, size=int(congested.sum()))
        rtts[leader] = 1e6  # exclude self from selection
        return rtts

    def expected_rtt_per_node(self, t: int = 0) -> np.ndarray:
        mu = self.base_rtt_matrix[0].copy()
        mu[0] = 1e6
        return mu


def run_ds2(n_rounds: int = 2000, n_seeds: int = 12, seed_base: int = 0):
    print("\n=== DS-2: Geo-distributed multi-cloud deployment ===\n")
    records = []
    for seed in range(n_seeds):
        rng = np.random.default_rng(seed_base + seed)
        net = GeoDistributedNetwork(rng=rng)
        oracle = MockOracle(window=50)
        baseline = BaselineRaftProtocol(N=9, k=3, window=50)
        is_raft = ISRaftProtocol(oracle, N=9, k=3)

        cache = [net.sample(t) for t in range(n_rounds)]
        history = []
        costs = {"baseline": [], "is_raft": []}
        for t in range(n_rounds):
            r_t = cache[t]
            H = np.array(history[-100:]) if history else np.zeros((0, 9))
            inp = OracleInput(rtt_history=H, vote_delays=np.zeros_like(H),
                              promote_outcomes=np.zeros_like(H), round_idx=t)
            costs["baseline"].append(baseline.run_round(r_t, inp).cost)
            costs["is_raft"].append(is_raft.run_round(r_t, inp).cost)
            history.append(r_t)
        b_arr = np.array(costs["baseline"])
        i_arr = np.array(costs["is_raft"])
        for proto, arr in [("baseline", b_arr), ("is_raft", i_arr)]:
            ci = bootstrap_ci(arr, np.mean, n_boot=1500)
            records.append({
                "seed": seed,
                "protocol": proto,
                "mean_cost_ms": ci.point,
                "ci_lo": ci.ci_lo,
                "ci_hi": ci.ci_hi,
                "p50_ms": float(np.percentile(arr, 50)),
                "p95_ms": float(np.percentile(arr, 95)),
                "p99_ms": float(np.percentile(arr, 99)),
            })
    df = pd.DataFrame(records)

    # Paired comparison across seeds
    print("Per-seed comparison:")
    print(df.to_string(index=False))

    # Aggregate
    agg = df.groupby("protocol").agg(
        mean_cost=("mean_cost_ms", "mean"),
        p99=("p99_ms", "mean"),
    ).reset_index()
    print("\nAggregated:")
    print(agg.to_string(index=False))

    # Statistical test
    b_seeds = df[df["protocol"] == "baseline"]["mean_cost_ms"].values
    i_seeds = df[df["protocol"] == "is_raft"]["mean_cost_ms"].values
    if len(b_seeds) == len(i_seeds):
        tr = paired_test(b_seeds, i_seeds, test="wilcoxon")
        print(f"\nPaired Wilcoxon (baseline vs is_raft): p={tr.pvalue:.4f}, "
              f"cohen_d={tr.effect_size:.3f}, sig={tr.significant}")
    out_dir = Path(__file__).resolve().parent / "results"
    out_dir.mkdir(exist_ok=True)
    df.to_csv(out_dir / "DS2_geo.csv", index=False)


if __name__ == "__main__":
    run_ds2()
