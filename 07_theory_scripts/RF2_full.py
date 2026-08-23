"""RF-2 full: 8 Raft variant comparison across multiple network conditions."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd

from is_raft.distributions import AdversarialNonStationary
from is_raft.oracle import PerfectOracle, MockOracle, OracleInput
from is_raft.protocol import (ISRaftProtocol, BaselineRaftProtocol,
                              RandomBaseline, RoundRobinBaseline, FixedSubsetBaseline)
from is_raft.stats import bootstrap_ci, paired_test, holm_correct

# Import additional baselines from RF2_variant_comparison
from experiments.RF2_variant_comparison import SCRaftBaseline, EtcdRaftBaseline


class CockroachStyleBaseline:
    """CockroachDB Multi-Raft-style: uses leader lease time + replica priority.
    Approximated as recent-success-weighted selection."""
    def __init__(self, N: int, k: int = 3, window: int = 30):
        self.N = N; self.k = k; self.window = window
        self.success_count = np.zeros(N)

    def run_round(self, r_t, history=None, rng=None):
        from is_raft.protocol import RoundOutcome
        if history is not None and history.rtt_history.shape[0] > 5:
            recent_rtts = history.rtt_history[-self.window:]
            mu = np.mean(recent_rtts, axis=0)
            scores = mu + 0.05 * (1.0 / (self.success_count + 1))
            cand = list(np.argsort(scores)[:self.k])
        else:
            cand = list(range(self.k))
        cost = float(np.min(r_t[cand]))
        selected = int(cand[int(np.argmin(r_t[cand]))])
        self.success_count[selected] += 1
        return RoundOutcome(cost=cost, used_oracle=False,
                            forecasted_cost=float("nan"),
                            actual_cost=cost, candidate_set=cand, selected=selected)


class TiKVStyleBaseline:
    """TiKV-style: round-robin among healthy replicas."""
    def __init__(self, N: int, k: int = 3, health_threshold: float = 2.0):
        self.N = N; self.k = k
        self.threshold = health_threshold
        self.next_idx = 0

    def run_round(self, r_t, history=None, rng=None):
        from is_raft.protocol import RoundOutcome
        if history is not None and history.rtt_history.shape[0] > 5:
            mu = np.mean(history.rtt_history[-30:], axis=0)
            healthy = np.where(mu < self.threshold * np.median(mu))[0]
            if len(healthy) >= self.k:
                cand = [(self.next_idx + i) % len(healthy) for i in range(self.k)]
                cand = [int(healthy[c]) for c in cand]
            else:
                cand = list(range(self.k))
            self.next_idx = (self.next_idx + self.k) % max(len(healthy), 1)
        else:
            cand = list(range(self.k))
        cost = float(np.min(r_t[cand]))
        selected = int(cand[int(np.argmin(r_t[cand]))])
        return RoundOutcome(cost=cost, used_oracle=False,
                            forecasted_cost=float("nan"),
                            actual_cost=cost, candidate_set=cand, selected=selected)


def run_full_comparison(N: int = 11, n_rounds: int = 2000,
                         shift_means=(5, 10, 25, 40), n_seeds: int = 5):
    cell_results = []
    pvalues = []
    pv_idx = []

    for sm in shift_means:
        per_seed_costs = {name: [] for name in [
            "Original Raft", "Round-Robin", "Fixed Subset",
            "S-Raft", "SCRaft", "etcd-Raft",
            "CockroachDB-style", "TiKV-style",
            "IS-Raft-MC (Mock)", "IS-Raft-MC (Perfect)",
        ]}
        for seed in range(n_seeds):
            local_rng = np.random.default_rng(seed * 100 + sm)
            dist = AdversarialNonStationary(N=N, fast_rate=1.0, slow_rate=10.0,
                                            shift_mean=sm,
                                            baseline_window_assumed=50,
                                            rng=local_rng)
            perfect = PerfectOracle(dist)
            mock = MockOracle(window=50)
            sample_cache = [dist.sample(t) for t in range(n_rounds)]

            variants = {
                "Original Raft":      RandomBaseline(N=N, k=3, seed=seed),
                "Round-Robin":        RoundRobinBaseline(N=N, k=3),
                "Fixed Subset":       FixedSubsetBaseline(N=N, k=3),
                "S-Raft":             BaselineRaftProtocol(N=N, k=3, window=50),
                "SCRaft":             SCRaftBaseline(N=N, k=3, window=30),
                "etcd-Raft":          EtcdRaftBaseline(N=N, k=3, window=100),
                "CockroachDB-style":  CockroachStyleBaseline(N=N, k=3, window=30),
                "TiKV-style":         TiKVStyleBaseline(N=N, k=3),
                "IS-Raft-MC (Mock)":   ISRaftProtocol(mock, N=N, k=3),
                "IS-Raft-MC (Perfect)": ISRaftProtocol(perfect, N=N, k=3),
            }
            seed_costs = {name: [] for name in variants}
            history = []
            for t in range(n_rounds):
                r_t = sample_cache[t]
                H = np.array(history[-100:]) if history else np.zeros((0, N))
                inp = OracleInput(rtt_history=H, vote_delays=np.zeros_like(H),
                                  promote_outcomes=np.zeros_like(H), round_idx=t)
                for name, proto in variants.items():
                    seed_costs[name].append(proto.run_round(r_t, inp).cost)
                history.append(r_t)
            for name, c in seed_costs.items():
                per_seed_costs[name].extend(c)

        # Compute statistics
        ref = np.array(per_seed_costs["IS-Raft-MC (Mock)"])
        ref_ci = bootstrap_ci(ref, np.mean, n_boot=2000)

        for name, c in per_seed_costs.items():
            arr = np.array(c)
            ci = bootstrap_ci(arr, np.mean, n_boot=2000)
            if name != "IS-Raft-MC (Mock)":
                tr = paired_test(arr, ref, test="wilcoxon")
                pvalues.append(tr.pvalue)
                pv_idx.append((sm, name))
                wp, cd = tr.pvalue, tr.effect_size
            else:
                wp, cd = float("nan"), float("nan")
            cell_results.append({
                "shift_mean": sm,
                "variant": name,
                "n_observations": len(arr),
                "cost_mean": ci.point,
                "cost_CI_lo": ci.ci_lo,
                "cost_CI_hi": ci.ci_hi,
                "vs_ISRaft_ratio": ci.point / ref_ci.point if ref_ci.point > 0 else float("nan"),
                "wilcoxon_p": wp,
                "cohen_d": cd,
            })

    sig = holm_correct(pvalues, alpha=0.05)
    sig_map = {idx: s for idx, s in zip(pv_idx, sig)}
    df = pd.DataFrame(cell_results)
    df["sig_holm"] = df.apply(
        lambda r: sig_map.get((r.shift_mean, r.variant), False),
        axis=1
    )
    return df


if __name__ == "__main__":
    print("\n=== RF-2 FULL: 10 Raft variants × 3 conditions × 5 seeds ===\n")
    df = run_full_comparison(n_rounds=1000, n_seeds=3)
    out = Path(__file__).resolve().parent / "results" / "RF2_full.csv"
    out.parent.mkdir(exist_ok=True)
    df.to_csv(out, index=False)
    for sm in sorted(df["shift_mean"].unique()):
        sub = df[df["shift_mean"] == sm]
        print(f"\n--- shift_mean = {sm} ---")
        cols = ["variant", "cost_mean", "vs_ISRaft_ratio", "wilcoxon_p", "cohen_d", "sig_holm"]
        print(sub[cols].to_string(index=False))
    print(f"\nTotal Holm-significant: {df['sig_holm'].sum()}/{(df['variant'] != 'IS-Raft-MC (Mock)').sum()}")
