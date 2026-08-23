"""Experiment E3 — Theorem E (BRAO): Byzantine-Robust Attention Oracle.

Sweeps f ∈ {0, 1, 2, 3} and ε ∈ {0.0, 0.5, 1.0, 2.0} for N=11.
Compares two oracle variants:
    - Bare PerfectOracle (no robustness) — degrades under f-perturbation
    - ByzantinePerturbedOracle with median aggregation (BRAO)
Verifies α degradation ≤ O(fLε/N) (Theorem E).
"""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from is_raft.distributions import NonStationaryHeavyTail
from is_raft.oracle import (PerfectOracle, MockOracle,
                            ByzantinePerturbedOracle, OracleInput)
from is_raft.protocol import ISRaftProtocol, BaselineRaftProtocol
from is_raft.lac_metrics import LACMetrics


def run_byzantine_sweep(N: int = 11, n_rounds: int = 500,
                        f_values=(0, 1, 2, 3),
                        eps_values=(0.0, 0.5, 1.0, 2.0),
                        seed: int = 0):
    rng = np.random.default_rng(seed)
    dist = NonStationaryHeavyTail(N=N, alpha=1.3, shift_period=50, rng=rng)
    # Use MockOracle (history-aware) so Byzantine perturbations actually affect prediction
    base_oracle = MockOracle(window=50)
    baseline = BaselineRaftProtocol(N=N, k=3)

    # Pre-sample for fair comparison
    history = []
    sample_cache, opts, bases = [], [], []
    for t in range(n_rounds):
        r_t = dist.sample(t)
        sample_cache.append(r_t)
        opts.append(float(np.min(r_t)))
        hist_arr = np.array(history[-100:]) if history else np.zeros((0, N))
        hist_input = OracleInput(rtt_history=hist_arr,
                                 vote_delays=np.zeros_like(hist_arr),
                                 promote_outcomes=np.zeros_like(hist_arr),
                                 round_idx=t)
        bases.append(baseline.run_round(r_t, hist_input).cost)
        history.append(r_t)
    opts = np.array(opts); bases = np.array(bases)

    records = []
    for f in f_values:
        for eps in eps_values:
            for variant in ("no_robust", "brao_median"):
                apply_median = (variant == "brao_median")
                byz = ByzantinePerturbedOracle(base_oracle, f=f, epsilon=eps,
                                               rng=rng, apply_median=apply_median)
                isr = ISRaftProtocol(byz, N=N, k=3)
                outcomes = []
                history2 = []
                for t in range(n_rounds):
                    r_t = sample_cache[t]
                    hist_arr = np.array(history2[-100:]) if history2 else np.zeros((0, N))
                    hist_input = OracleInput(rtt_history=hist_arr,
                                             vote_delays=np.zeros_like(hist_arr),
                                             promote_outcomes=np.zeros_like(hist_arr),
                                             round_idx=t)
                    outcomes.append(isr.run_round(r_t, hist_input))
                    history2.append(r_t)
                m = LACMetrics.from_outcomes(outcomes, opts, bases)
                records.append({"f": f, "epsilon": eps, "variant": variant,
                                "alpha": m.alpha, "beta": m.beta, "N": N})
    df = pd.DataFrame(records)
    return df


if __name__ == "__main__":
    df = run_byzantine_sweep()
    out_dir = Path(__file__).resolve().parent / "results"
    out_dir.mkdir(exist_ok=True)
    df.to_csv(out_dir / "E3_byzantine.csv", index=False)
    print("\n=== E3 BRAO verification - Theorem E ===")
    print(df.to_string(index=False))
    print(f"\nSaved to {out_dir}")
