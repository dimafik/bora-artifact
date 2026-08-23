"""Experiment E4 — Theorem D: Calibrated Predictive Liveness.

Measures (ζ, κ)-CPL for:
    - BaselineRaftProtocol (classical finite-memory): expected to fail
      non-vacuous CPL — high ζ, κ far from 1.
    - ISRaftProtocol with MockOracle (PAC-learnable): expected to achieve
      ζ → 0 as T → ∞, κ → 1.
Confirms classical impossibility (Lemma D-1) and LAC achievability (Lemma D-2).
"""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from is_raft.distributions import NonStationaryHeavyTail
from is_raft.oracle import MockOracle, OracleInput
from is_raft.protocol import ISRaftProtocol, BaselineRaftProtocol
from is_raft.lac_metrics import CPLMetrics


def run_cpl_experiment(N: int = 11, T_values=(50, 100, 250, 500, 1000),
                       seed: int = 0):
    rng = np.random.default_rng(seed)
    records = []
    for T in T_values:
        dist = NonStationaryHeavyTail(N=N, alpha=1.3, shift_period=50, rng=rng)
        baseline = BaselineRaftProtocol(N=N, k=3)
        mock = MockOracle(window=50)
        isr = ISRaftProtocol(mock, N=N, k=3)

        history_b, history_isr = [], []
        outcomes_b, outcomes_isr = [], []
        for t in range(T):
            r_t = dist.sample(t)
            hist_b = np.array(history_b[-100:]) if history_b else np.zeros((0, N))
            hist_isr = np.array(history_isr[-100:]) if history_isr else np.zeros((0, N))
            inp_b = OracleInput(rtt_history=hist_b,
                                vote_delays=np.zeros_like(hist_b),
                                promote_outcomes=np.zeros_like(hist_b), round_idx=t)
            inp_isr = OracleInput(rtt_history=hist_isr,
                                  vote_delays=np.zeros_like(hist_isr),
                                  promote_outcomes=np.zeros_like(hist_isr), round_idx=t)
            outcomes_b.append(baseline.run_round(r_t, inp_b))
            outcomes_isr.append(isr.run_round(r_t, inp_isr))
            history_b.append(r_t)
            history_isr.append(r_t)

        cpl_b = CPLMetrics.from_outcomes(outcomes_b)
        cpl_isr = CPLMetrics.from_outcomes(outcomes_isr)
        records.append({"T": T, "protocol": "baseline",
                        "zeta": cpl_b.zeta, "kappa": cpl_b.kappa, "N": N})
        records.append({"T": T, "protocol": "is_raft",
                        "zeta": cpl_isr.zeta, "kappa": cpl_isr.kappa, "N": N})
    return pd.DataFrame(records)


if __name__ == "__main__":
    df = run_cpl_experiment()
    out_dir = Path(__file__).resolve().parent / "results"
    out_dir.mkdir(exist_ok=True)
    df.to_csv(out_dir / "E4_cpl.csv", index=False)
    print("\n=== E4 CPL - Theorem D verification ===")
    print(df.to_string(index=False))
    print("\nExpected: baseline zeta stays large; is_raft zeta -> 0 as T grows")
    print(f"Saved to {out_dir}")
