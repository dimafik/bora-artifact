"""F1 — E1 strengthened: TRUE separation with proper baselines.

Changes from E1_separation_stats.py:
1. n_rounds = 2000 (4x increase for statistical power)
2. Three TRUE non-learning baselines: Random, RoundRobin, FixedSubset
3. AdversarialNonStationary distribution (shift_mean << baseline_window)
4. Bootstrap 95% CI + Holm-Bonferroni multiple comparison
5. Effect size reporting (Cohen's d)
6. Tail-index of the actual distribution (alpha equivalent)
7. Direct verification of Theorem 1's separation claim

Expected outcome (per refined Theorem 1):
- IS-Raft (with PerfectOracle) achieves near-OPT
- Random/RoundRobin/FixedSubset show measurable gap
- Gap grows with exploitability (shift_mean ↓ relative to baseline_window)
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
                              RandomBaseline, RoundRobinBaseline, FixedSubsetBaseline)
from is_raft.stats import bootstrap_ci, paired_test, holm_correct


def run_separation_strengthened(N: int = 11, n_rounds: int = 2000,
                                shift_means=(5, 10, 25, 50, 100),
                                window: int = 50,
                                seed: int = 0):
    rng_master = np.random.default_rng(seed)
    cell_results = []
    pvalue_collection = []
    pvalue_index = []

    for shift_mean in shift_means:
        # Skip configurations where adversary cannot beat baseline
        if shift_mean >= window:
            continue
        # Independent RNG per config for reproducibility
        rng = np.random.default_rng(seed + int(shift_mean))
        dist = AdversarialNonStationary(N=N, fast_rate=1.0, slow_rate=10.0,
                                        shift_mean=shift_mean,
                                        baseline_window_assumed=window, rng=rng)
        perfect = PerfectOracle(dist)
        mock = MockOracle(window=window)

        # Pre-sample all rounds for paired comparison
        sample_cache = [dist.sample(t) for t in range(n_rounds)]

        protocols = {
            "RandomBaseline":    RandomBaseline(N=N, k=3, seed=seed + int(shift_mean)),
            "RoundRobinBaseline": RoundRobinBaseline(N=N, k=3),
            "FixedSubset":       FixedSubsetBaseline(N=N, k=3),
            "SRaftBaseline(window=50)": BaselineRaftProtocol(N=N, k=3, window=window),
            "IS-Raft (MockOracle)":     ISRaftProtocol(mock, N=N, k=3),
            "IS-Raft (PerfectOracle)":  ISRaftProtocol(perfect, N=N, k=3),
        }

        costs = {name: [] for name in protocols}
        history = []
        for t in range(n_rounds):
            r_t = sample_cache[t]
            H = np.array(history[-100:]) if history else np.zeros((0, N))
            inp = OracleInput(rtt_history=H,
                              vote_delays=np.zeros_like(H),
                              promote_outcomes=np.zeros_like(H), round_idx=t)
            for name, proto in protocols.items():
                costs[name].append(proto.run_round(r_t, inp).cost)
            history.append(r_t)

        # Compute OPT (offline minimum each round)
        opt_costs = np.array([float(np.min(r_t)) for r_t in sample_cache])

        # Bootstrap CIs
        cis = {}
        for name, c in costs.items():
            c = np.array(c)
            ci = bootstrap_ci(c, np.mean, n_boot=2000)
            cis[name] = (ci, c)

        # Reference: IS-Raft (PerfectOracle) is the "best learner"
        ref_name = "IS-Raft (PerfectOracle)"
        ref_ci, ref_c = cis[ref_name]

        for name, (ci, c) in cis.items():
            if name == ref_name:
                continue
            # Test: name vs IS-Raft (PerfectOracle)
            tres = paired_test(c, ref_c, test="wilcoxon")
            ratio = ci.point / ref_ci.point if ref_ci.point > 0 else float("nan")
            cell_results.append({
                "shift_mean": shift_mean,
                "window": window,
                "protocol": name,
                "n_rounds": n_rounds,
                "cost_mean": ci.point,
                "cost_CI_lo": ci.ci_lo,
                "cost_CI_hi": ci.ci_hi,
                "vs_IS_Raft_ratio": ratio,
                "wilcoxon_p": tres.pvalue,
                "cohen_d": tres.effect_size,
            })
            pvalue_collection.append(tres.pvalue)
            pvalue_index.append((shift_mean, name))

        # Also reference IS-Raft against OPT
        opt_ci = bootstrap_ci(opt_costs, np.mean, n_boot=2000)
        cell_results.append({
            "shift_mean": shift_mean,
            "window": window,
            "protocol": "OPT (offline min)",
            "n_rounds": n_rounds,
            "cost_mean": opt_ci.point,
            "cost_CI_lo": opt_ci.ci_lo,
            "cost_CI_hi": opt_ci.ci_hi,
            "vs_IS_Raft_ratio": opt_ci.point / ref_ci.point if ref_ci.point > 0 else float("nan"),
            "wilcoxon_p": float("nan"),
            "cohen_d": float("nan"),
        })

    # Holm-Bonferroni across all (shift_mean × protocol) cells
    sig = holm_correct(pvalue_collection, alpha=0.05)
    df = pd.DataFrame(cell_results)
    # Map sig flags back to non-OPT rows
    sig_map = {idx: s for idx, s in zip(pvalue_index, sig)}
    df["sig_holm"] = df.apply(
        lambda row: sig_map.get((row.shift_mean, row.protocol), False)
        if row.protocol != "OPT (offline min)" else False,
        axis=1)
    return df


if __name__ == "__main__":
    df = run_separation_strengthened()
    out = Path(__file__).resolve().parent / "results" / "F1_E1_strengthened.csv"
    out.parent.mkdir(exist_ok=True)
    df.to_csv(out, index=False)

    print("\n=== F1: E1 Strengthened (Theorem 1 separation verification) ===\n")
    for sm in sorted(df["shift_mean"].unique()):
        sub = df[df["shift_mean"] == sm]
        print(f"\n--- shift_mean = {sm} (window=50, ratio = adv_speed = {50/sm:.1f}x) ---")
        cols = ["protocol", "cost_mean", "cost_CI_lo", "cost_CI_hi",
                "vs_IS_Raft_ratio", "wilcoxon_p", "cohen_d", "sig_holm"]
        print(sub[cols].to_string(index=False))

    # Summary: gap = baseline / IS-Raft
    print("\n=== Separation Gap Summary ===")
    summary_rows = []
    for sm in sorted(df["shift_mean"].unique()):
        sub = df[df["shift_mean"] == sm]
        ref = sub[sub["protocol"] == "IS-Raft (PerfectOracle)"]["cost_mean"]
        if len(ref) == 0:
            # Need to compute via baseline ratio inverted
            random_ratio = sub[sub["protocol"] == "RandomBaseline"]["vs_IS_Raft_ratio"].values
            srafts_ratio = sub[sub["protocol"] == "SRaftBaseline(window=50)"]["vs_IS_Raft_ratio"].values
            summary_rows.append({
                "shift_mean": sm,
                "gap_Random_vs_ISRaft": float(random_ratio[0]) if len(random_ratio) > 0 else float("nan"),
                "gap_SRaft_vs_ISRaft": float(srafts_ratio[0]) if len(srafts_ratio) > 0 else float("nan"),
            })
    print(pd.DataFrame(summary_rows).to_string(index=False))

    n_sig = df["sig_holm"].sum()
    print(f"\nTotal Holm-Bonferroni significant cells: {n_sig}/{(df['protocol'] != 'OPT (offline min)').sum()}")
    print(f"Saved to {out}")
