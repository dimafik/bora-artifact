"""E1 enhanced with statistical rigor.

Re-runs Theorem 1 separation experiment with:
- 95% bootstrap CI on every reported number
- Paired Wilcoxon test (baseline vs IS-Raft variants)
- Cohen's d / Cliff's delta effect size
- Holm-Bonferroni multiple-comparison correction across (regime, alpha) cells

Output ready for paper Table 1 reporting (with stat sig flags).
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd

from is_raft.distributions import StationaryPareto, NonStationaryHeavyTail
from is_raft.oracle import PerfectOracle, MockOracle, OracleInput
from is_raft.protocol import ISRaftProtocol, BaselineRaftProtocol
from is_raft.stats import bootstrap_ci, paired_test, holm_correct


def run_stats_sweep(N: int = 11, n_rounds: int = 500, history_len: int = 100,
                    alphas=(0.8, 1.0, 1.2, 1.5, 2.0, 3.0), seed: int = 0):
    rng = np.random.default_rng(seed)
    cell_results = []
    pvalue_collection = []
    pvalue_index = []

    for regime in ("stationary", "nonstationary"):
        for alpha in alphas:
            if regime == "stationary":
                dist = StationaryPareto(N=N, r_min=1.0, alpha=alpha, rng=rng)
            else:
                dist = NonStationaryHeavyTail(N=N, alpha=alpha, shift_period=50, rng=rng)

            oracle_p = PerfectOracle(dist)
            oracle_m = MockOracle(window=50)
            baseline = BaselineRaftProtocol(N=N, k=3)
            isr_p = ISRaftProtocol(oracle_p, N=N, k=3)
            isr_m = ISRaftProtocol(oracle_m, N=N, k=3)

            history = []
            costs_b, costs_p, costs_m = [], [], []
            for t in range(n_rounds):
                r_t = dist.sample(t)
                H = np.array(history[-history_len:]) if history else np.zeros((0, N))
                inp = OracleInput(rtt_history=H,
                                  vote_delays=np.zeros_like(H),
                                  promote_outcomes=np.zeros_like(H), round_idx=t)
                costs_b.append(baseline.run_round(r_t, inp).cost)
                costs_p.append(isr_p.run_round(r_t, inp).cost)
                costs_m.append(isr_m.run_round(r_t, inp).cost)
                history.append(r_t)

            costs_b = np.array(costs_b); costs_p = np.array(costs_p); costs_m = np.array(costs_m)

            # Bootstrap CI on means
            ci_b = bootstrap_ci(costs_b, np.mean, n_boot=2000)
            ci_p = bootstrap_ci(costs_p, np.mean, n_boot=2000)
            ci_m = bootstrap_ci(costs_m, np.mean, n_boot=2000)

            # Paired tests
            t_bp = paired_test(costs_b, costs_p)
            t_bm = paired_test(costs_b, costs_m)
            pvalue_collection.extend([t_bp.pvalue, t_bm.pvalue])
            pvalue_index.extend([(regime, alpha, "is_raft_perfect"),
                                 (regime, alpha, "is_raft_mock")])

            cell_results.append({
                "regime": regime, "alpha": alpha, "N": N,
                "baseline_mean": ci_b.point,
                "baseline_CI": f"[{ci_b.ci_lo:.3f}, {ci_b.ci_hi:.3f}]",
                "is_raft_perfect_mean": ci_p.point,
                "is_raft_perfect_CI": f"[{ci_p.ci_lo:.3f}, {ci_p.ci_hi:.3f}]",
                "is_raft_mock_mean": ci_m.point,
                "is_raft_mock_CI": f"[{ci_m.ci_lo:.3f}, {ci_m.ci_hi:.3f}]",
                "gap_perfect": ci_b.point / ci_p.point if ci_p.point > 0 else float("nan"),
                "gap_mock": ci_b.point / ci_m.point if ci_m.point > 0 else float("nan"),
                "wilcoxon_p_perfect": t_bp.pvalue,
                "cohen_d_perfect": t_bp.effect_size,
                "wilcoxon_p_mock": t_bm.pvalue,
                "cohen_d_mock": t_bm.effect_size,
            })

    # Holm-Bonferroni across all cells
    sig_flags = holm_correct(pvalue_collection, alpha=0.05)
    df = pd.DataFrame(cell_results)
    # Map flags back
    holm_perfect = [sig_flags[pvalue_index.index((row.regime, row.alpha, "is_raft_perfect"))]
                    for row in df.itertuples()]
    holm_mock = [sig_flags[pvalue_index.index((row.regime, row.alpha, "is_raft_mock"))]
                 for row in df.itertuples()]
    df["sig_holm_perfect"] = holm_perfect
    df["sig_holm_mock"] = holm_mock
    return df


if __name__ == "__main__":
    df = run_stats_sweep()
    out = Path(__file__).resolve().parent / "results" / "E1_with_stats.csv"
    out.parent.mkdir(exist_ok=True)
    df.to_csv(out, index=False)
    print("\n=== E1 with Statistical Rigor (Theorem 1) ===")
    cols = ["regime", "alpha", "baseline_mean", "is_raft_perfect_mean",
            "gap_perfect", "wilcoxon_p_perfect", "cohen_d_perfect",
            "sig_holm_perfect"]
    print(df[cols].to_string(index=False))
    n_sig = df["sig_holm_perfect"].sum()
    print(f"\nHolm-Bonferroni significant cells (perfect vs baseline): {n_sig}/{len(df)}")
    print(f"Saved to {out}")
