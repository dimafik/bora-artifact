"""RF-2: Raft variant comparison (5-9 variants).

Compares throughput, latency, deadline misses across:
  - Original Raft (random + history-oblivious)
  - S-Raft (RTT-min with sliding window)
  - SCRaft (priority-aware single successor)
  - etcd-style Raft (median-of-history)
  - IS-Raft-MC (ours, with oracle + MC)

Pilot: 5 variants. Full: + Atomix-style, Fabric-style, TiKV-style, original.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd

from is_raft.distributions import AdversarialNonStationary
from is_raft.oracle import PerfectOracle, MockOracle, OracleInput
from is_raft.protocol import (ISRaftProtocol, BaselineRaftProtocol,
                              RandomBaseline, RoundRobinBaseline)
from is_raft.stats import bootstrap_ci, paired_test, holm_correct


class SCRaftBaseline:
    """SCRaft (HPCC'24 Wang et al.): priority-timer-based single successor.
    Selects deterministically the lowest-RTT node as priority successor."""
    def __init__(self, N: int, k: int = 3, window: int = 30):
        self.N = N; self.k = k; self.window = window

    def run_round(self, r_t, history=None, rng=None):
        from is_raft.protocol import RoundOutcome
        if history is not None and history.rtt_history.shape[0] > 0:
            mu = np.mean(history.rtt_history[-self.window:], axis=0)
            cand = list(np.argsort(mu)[:self.k])
        else:
            cand = list(range(self.k))
        cost = float(np.min(r_t[cand]))
        selected = int(cand[int(np.argmin(r_t[cand]))])
        return RoundOutcome(cost=cost, used_oracle=False,
                            forecasted_cost=float("nan"),
                            actual_cost=cost, candidate_set=cand, selected=selected)


class EtcdRaftBaseline:
    """etcd-style Raft: uses last-heartbeat-time + p99 latency for leader choice.
    Approximates with median-of-window."""
    def __init__(self, N: int, k: int = 3, window: int = 100):
        self.N = N; self.k = k; self.window = window

    def run_round(self, r_t, history=None, rng=None):
        from is_raft.protocol import RoundOutcome
        rng = rng or np.random.default_rng(0)
        if history is not None and history.rtt_history.shape[0] > 5:
            recent = history.rtt_history[-self.window:]
            scores = np.percentile(recent, 99, axis=0)
            cand = list(np.argsort(scores)[:self.k])
        else:
            cand = list(rng.choice(self.N, size=self.k, replace=False))
        cost = float(np.min(r_t[cand]))
        selected = int(cand[int(np.argmin(r_t[cand]))])
        return RoundOutcome(cost=cost, used_oracle=False,
                            forecasted_cost=float("nan"),
                            actual_cost=cost, candidate_set=cand, selected=selected)


def run_variant_comparison(N: int = 11, n_rounds: int = 1000,
                            shift_means=(10, 25), seed: int = 0):
    rng = np.random.default_rng(seed)
    cell_results = []
    pvalues = []
    pv_idx = []

    for sm in shift_means:
        local_rng = np.random.default_rng(seed + sm)
        dist = AdversarialNonStationary(N=N, fast_rate=1.0, slow_rate=10.0,
                                        shift_mean=sm, baseline_window_assumed=50,
                                        rng=local_rng)
        perfect = PerfectOracle(dist)
        mock = MockOracle(window=50)
        sample_cache = [dist.sample(t) for t in range(n_rounds)]

        variants = {
            "Original Raft":      RandomBaseline(N=N, k=3, seed=seed),
            "S-Raft":             BaselineRaftProtocol(N=N, k=3, window=50),
            "SCRaft":             SCRaftBaseline(N=N, k=3, window=30),
            "etcd-Raft":          EtcdRaftBaseline(N=N, k=3, window=100),
            "IS-Raft-MC (Perfect)": ISRaftProtocol(perfect, N=N, k=3),
            "IS-Raft-MC (Mock)":   ISRaftProtocol(mock, N=N, k=3),
        }
        costs = {name: [] for name in variants}
        history = []
        for t in range(n_rounds):
            r_t = sample_cache[t]
            H = np.array(history[-100:]) if history else np.zeros((0, N))
            inp = OracleInput(rtt_history=H, vote_delays=np.zeros_like(H),
                              promote_outcomes=np.zeros_like(H), round_idx=t)
            for name, proto in variants.items():
                costs[name].append(proto.run_round(r_t, inp).cost)
            history.append(r_t)

        # Reference = IS-Raft-MC (Mock) — realistic LAC
        ref = np.array(costs["IS-Raft-MC (Mock)"])
        ref_ci = bootstrap_ci(ref, np.mean, n_boot=2000)
        for name, c in costs.items():
            arr = np.array(c)
            ci = bootstrap_ci(arr, np.mean, n_boot=2000)
            t_res = paired_test(arr, ref) if name != "IS-Raft-MC (Mock)" \
                else None
            cell_results.append({
                "shift_mean": sm,
                "variant": name,
                "cost_mean": ci.point,
                "cost_CI_lo": ci.ci_lo,
                "cost_CI_hi": ci.ci_hi,
                "vs_ISRaft_ratio": ci.point / ref_ci.point if ref_ci.point > 0 else float("nan"),
                "wilcoxon_p": t_res.pvalue if t_res else float("nan"),
                "cohen_d": t_res.effect_size if t_res else float("nan"),
            })
            if t_res:
                pvalues.append(t_res.pvalue)
                pv_idx.append((sm, name))
    # Holm correction
    sig = holm_correct(pvalues, alpha=0.05)
    sig_map = {idx: s for idx, s in zip(pv_idx, sig)}
    df = pd.DataFrame(cell_results)
    df["sig_holm"] = df.apply(
        lambda r: sig_map.get((r.shift_mean, r.variant), False),
        axis=1
    )
    return df


if __name__ == "__main__":
    print("\n=== RF-2 mini: 6 Raft variant comparison ===\n")
    df = run_variant_comparison()
    out = Path(__file__).resolve().parent / "results" / "RF2_pilot.csv"
    out.parent.mkdir(exist_ok=True)
    df.to_csv(out, index=False)
    for sm in sorted(df["shift_mean"].unique()):
        sub = df[df["shift_mean"] == sm]
        print(f"\n--- shift_mean = {sm} ---")
        cols = ["variant", "cost_mean", "cost_CI_lo", "cost_CI_hi",
                "vs_ISRaft_ratio", "wilcoxon_p", "cohen_d", "sig_holm"]
        print(sub[cols].to_string(index=False))
    n_sig = df["sig_holm"].sum()
    print(f"\nTotal Holm-significant cells: {n_sig}/{(df['variant'] != 'IS-Raft-MC (Mock)').sum()}")
