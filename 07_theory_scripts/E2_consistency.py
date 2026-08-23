"""Experiment E2 — Theorem B & C: Consistency-robustness Pareto frontier.

Sweeps oracle noise τ ∈ {0, 0.05, 0.1, 0.2, 0.5, 1.0} and measures
(α, β, γ) of IS-Raft against PerfectOracle and AdversarialOracle.
Output:
    - α vs τ curve (consistency)
    - β under adversarial oracle (robustness)
    - γ from α(τ) slope (smoothness)
    - Pareto frontier verification matching Theorem C: (α-1)(β-1) ≥ Ω(1/√N)
"""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from is_raft.distributions import NonStationaryHeavyTail
from is_raft.oracle import PerfectOracle, NoisyOracle, AdversarialOracle, OracleInput
from is_raft.protocol import ISRaftProtocol, BaselineRaftProtocol
from is_raft.lac_metrics import LACMetrics, smoothness_slope


def run_consistency_sweep(N: int = 11, n_rounds: int = 500,
                          taus=(0.0, 0.05, 0.1, 0.2, 0.5, 1.0),
                          alpha_pareto: float = 1.3,
                          seed: int = 0):
    rng = np.random.default_rng(seed)
    dist = NonStationaryHeavyTail(N=N, alpha=alpha_pareto, shift_period=50, rng=rng)
    perfect = PerfectOracle(dist)
    adversarial = AdversarialOracle(dist)
    baseline = BaselineRaftProtocol(N=N, k=3)

    # Precompute OPT and BASE per round
    history = []
    opts, bases = [], []
    sample_cache = []
    for t in range(n_rounds):
        r_t = dist.sample(t)
        sample_cache.append(r_t)
        opts.append(float(np.min(r_t)))  # offline min
        hist_arr = np.array(history[-100:]) if history else np.zeros((0, N))
        hist_input = OracleInput(rtt_history=hist_arr,
                                 vote_delays=np.zeros_like(hist_arr),
                                 promote_outcomes=np.zeros_like(hist_arr),
                                 round_idx=t)
        bases.append(baseline.run_round(r_t, hist_input).cost)
        history.append(r_t)

    opts = np.array(opts)
    bases = np.array(bases)

    records = []
    for tau in taus:
        noisy = NoisyOracle(perfect, tau=tau, rng=rng)
        isr = ISRaftProtocol(noisy, N=N, k=3)
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
        records.append({"oracle": "noisy", "tau": tau, "alpha": m.alpha,
                        "beta": m.beta, "N": N})

    # Adversarial oracle for robustness measurement
    isr_adv = ISRaftProtocol(adversarial, N=N, k=3)
    outcomes_adv = []
    history3 = []
    for t in range(n_rounds):
        r_t = sample_cache[t]
        hist_arr = np.array(history3[-100:]) if history3 else np.zeros((0, N))
        hist_input = OracleInput(rtt_history=hist_arr,
                                 vote_delays=np.zeros_like(hist_arr),
                                 promote_outcomes=np.zeros_like(hist_arr),
                                 round_idx=t)
        outcomes_adv.append(isr_adv.run_round(r_t, hist_input))
        history3.append(r_t)
    m_adv = LACMetrics.from_outcomes(outcomes_adv, opts, bases)
    records.append({"oracle": "adversarial", "tau": float("inf"),
                    "alpha": m_adv.alpha, "beta": m_adv.beta, "N": N})

    df = pd.DataFrame(records)
    # γ slope from non-inf τ
    noisy_rows = df[df["oracle"] == "noisy"]
    gamma = smoothness_slope(noisy_rows["tau"].tolist(), noisy_rows["alpha"].tolist())
    df.attrs["gamma"] = gamma

    # Verify Theorem C: (α-1)(β-1) ≥ Ω(1/√N)
    df["pareto_product"] = (df["alpha"] - 1) * (df["beta"] - 1)
    df["theorem_C_bound"] = 1.0 / np.sqrt(N)
    return df


if __name__ == "__main__":
    df = run_consistency_sweep()
    out_dir = Path(__file__).resolve().parent / "results"
    out_dir.mkdir(exist_ok=True)
    df.to_csv(out_dir / "E2_consistency.csv", index=False)
    print("\n=== E2 (alpha, beta) sweep - Theorem B + C ===")
    print(df.to_string(index=False))
    print(f"\nSmoothness gamma = {df.attrs['gamma']:.4f}")
    print(f"Saved to {out_dir}")
