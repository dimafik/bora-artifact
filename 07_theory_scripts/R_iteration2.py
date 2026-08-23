"""Iteration 2: refinements based on Round 62 panel feedback.

R1-v2: Temperature-scaled calibration (Guo 2017)
M5-v2: 100-trial smoothness γ measurement (was n=12)
R7-v2: Improved coalition simulation with proper incentive structure
"""
from __future__ import annotations
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd

from is_raft.distributions import AdversarialNonStationary
from is_raft.oracle import (MockOracle, PerfectOracle, NoisyOracle, OracleInput)
from is_raft.protocol import ISRaftProtocol, BaselineRaftProtocol
from is_raft.stats import bootstrap_ci, paired_test


# ============================================================
# R1-v2: Temperature-scaled calibration
# ============================================================
def r1_v2_temperature_calibration():
    """Apply temperature scaling to fix ECE = 0.72 issue.

    Guo et al. 2017: softmax(logits / T) for T > 1 makes probabilities
    more spread; T < 1 makes them sharper.
    """
    print("\n=== R1-v2: Temperature-Scaled Calibration ===\n")
    N = 11
    n_rounds = 5000
    n_seeds = 5
    temperatures = [0.5, 1.0, 2.0, 5.0, 10.0]
    records = []
    for T in temperatures:
        for seed in range(n_seeds):
            rng = np.random.default_rng(seed)
            dist = AdversarialNonStationary(N=N, shift_mean=10,
                                              baseline_window_assumed=50, rng=rng)
            oracle = MockOracle(window=50)
            isr = ISRaftProtocol(oracle, N=N, k=3)
            sample_cache = [dist.sample(t) for t in range(n_rounds)]
            history = []
            predictions = []
            outcomes = []
            for t in range(n_rounds):
                r_t = sample_cache[t]
                H = np.array(history[-100:]) if history else np.zeros((0, N))
                inp = OracleInput(rtt_history=H, vote_delays=np.zeros_like(H),
                                  promote_outcomes=np.zeros_like(H), round_idx=t)
                out = isr.run_round(r_t, inp)
                p = oracle.predict(inp)
                # Apply temperature scaling: p^(1/T) / sum
                p_scaled = p ** (1.0 / T)
                p_scaled = p_scaled / p_scaled.sum()
                confidence = float(p_scaled[out.selected])
                median_rtt = float(np.median(r_t))
                outcome = int(out.cost < median_rtt)
                predictions.append(confidence)
                outcomes.append(outcome)
                history.append(r_t)
            predictions = np.array(predictions)
            outcomes = np.array(outcomes)
            # ECE with 10 bins
            n_bins = 10
            bins = np.linspace(predictions.min(), predictions.max() + 1e-9, n_bins + 1)
            ece = 0.0
            n_total = len(predictions)
            for b in range(n_bins):
                mask = (predictions >= bins[b]) & (predictions < bins[b+1])
                if mask.sum() > 0:
                    pred = predictions[mask].mean()
                    emp = outcomes[mask].mean()
                    ece += abs(pred - emp) * mask.sum() / n_total
            brier = float(np.mean((predictions - outcomes) ** 2))
            records.append({
                "T": T, "seed": seed,
                "ECE": float(ece), "Brier": brier,
            })
    df = pd.DataFrame(records)
    out = Path(__file__).resolve().parent / "results" / "R1v2_temperature.csv"
    df.to_csv(out, index=False)
    agg = df.groupby("T").agg(
        ECE_mean=("ECE", "mean"),
        ECE_std=("ECE", "std"),
        Brier_mean=("Brier", "mean"),
    ).reset_index()
    print("Temperature-scaled calibration:")
    print(agg.to_string(index=False))
    best_T = float(agg.loc[agg["ECE_mean"].idxmin(), "T"])
    best_ECE = float(agg["ECE_mean"].min())
    print(f"\nOptimal T = {best_T}, best ECE = {best_ECE:.4f}")
    print(f"Original ECE = 0.72 (without temperature scaling)")
    return df


# ============================================================
# M5-v2: 100-trial smoothness γ
# ============================================================
def m5_v2_smoothness_100trial():
    """High-precision smoothness gamma with n=100 (was 12)."""
    print("\n=== M5-v2: Smoothness gamma - 100 trials ===\n")
    N = 11
    n_rounds = 1000
    n_seeds = 100
    taus = [0.0, 0.05, 0.1, 0.2, 0.3, 0.5, 0.8, 1.0]
    records = []
    for seed in range(n_seeds):
        rng = np.random.default_rng(seed)
        dist = AdversarialNonStationary(N=N, shift_mean=10,
                                          baseline_window_assumed=50, rng=rng)
        perfect = PerfectOracle(dist)
        sample_cache = [dist.sample(t) for t in range(n_rounds)]
        for tau in taus:
            noisy = NoisyOracle(perfect, tau=tau, rng=rng)
            isr = ISRaftProtocol(noisy, N=N, k=3)
            history = []
            costs = []
            for t in range(n_rounds):
                r_t = sample_cache[t]
                H = np.array(history[-100:]) if history else np.zeros((0, N))
                inp = OracleInput(rtt_history=H, vote_delays=np.zeros_like(H),
                                  promote_outcomes=np.zeros_like(H), round_idx=t)
                costs.append(isr.run_round(r_t, inp).cost)
                history.append(r_t)
            records.append({
                "seed": seed, "tau": tau,
                "alpha": float(np.mean(costs) / np.mean([np.min(c) for c in sample_cache])),
            })
        if (seed + 1) % 25 == 0:
            print(f"  Trial {seed+1}/100 done...")
    df = pd.DataFrame(records)
    # Fit gamma per seed
    gammas = []
    for seed in range(n_seeds):
        sub = df[df["seed"] == seed]
        if len(sub) >= 4:
            slope = float(np.polyfit(sub["tau"], sub["alpha"], 1)[0])
            gammas.append(slope)
    gamma_ci = bootstrap_ci(np.array(gammas), np.mean, n_boot=5000)
    print(f"\nEmpirical smoothness gamma (100 trials):")
    print(f"  Mean: {gamma_ci}")
    print(f"  Std:  {np.std(gammas):.3f}")
    print(f"  Min:  {np.min(gammas):.3f}")
    print(f"  Max:  {np.max(gammas):.3f}")
    print(f"  Theoretical: gamma = sqrt(N) = {np.sqrt(N):.2f}")
    out = Path(__file__).resolve().parent / "results" / "M5v2_smoothness.csv"
    df.to_csv(out, index=False)
    return df


# ============================================================
# R7-v2: Improved coalition simulation
# ============================================================
def r7_v2_coalition_corrected():
    """Coalition simulation with corrected incentive logic.

    Coalition coordinates: both choose to misreport in same direction.
    Pre-commitment forces independent decisions: no coordination.

    Properly modeled:
      - utility = reward + mev - slash
      - reward only when |individual deviation| < threshold
      - mev only when coalition is selected as sub-leader (requires
        coordinated misreport)
      - slash = lambda * |deviation| if > threshold
    """
    print("\n=== R7-v2: Coalition Resistance (Corrected) ===\n")
    records = []
    sigma = 32.0
    mu = 10.0  # MEV opportunity (higher than before)
    lambda_slash = 5.0
    theta = 0.5
    p_detect = 0.7  # detection probability when MEV occurs
    epsilons = [0.0, 0.1, 0.3, 0.5, 1.0, 2.0]
    for eps in epsilons:
        for use_precommit in [False, True]:
            for trial in range(100):
                rng = np.random.default_rng(trial + int(eps * 100))
                if use_precommit:
                    # Independent decisions; each commits before seeing other
                    # MEV requires *both* to misreport same direction (low prob)
                    delta_1 = eps if rng.random() < 0.5 else -eps
                    delta_2 = eps if rng.random() < 0.5 else -eps
                    coordinated = (delta_1 == delta_2)
                else:
                    # Coordinated misreport: both same direction
                    delta_1 = delta_2 = eps
                    coordinated = True
                # Individual deviation magnitudes
                dev_1 = abs(delta_1)
                dev_2 = abs(delta_2)
                # Slash if individual > threshold
                slash = lambda_slash * (max(0, dev_1 - theta) + max(0, dev_2 - theta))
                # MEV requires coordination + undetected
                if coordinated and eps > 0:
                    mev_gain = mu * (1 - p_detect)
                else:
                    mev_gain = 0
                # Reward only if not slashed
                reward = sigma * 0.05 * (1.0 if (dev_1 < theta and dev_2 < theta) else 0)
                # Coalition's joint utility
                utility = reward + mev_gain - slash
                honest_utility = sigma * 0.05
                records.append({
                    "epsilon": eps,
                    "precommit": use_precommit,
                    "trial": trial,
                    "coordinated": coordinated,
                    "coalition_utility": utility,
                    "advantage_vs_honest": utility - honest_utility,
                })
    df = pd.DataFrame(records)
    out = Path(__file__).resolve().parent / "results" / "R7v2_coalition.csv"
    df.to_csv(out, index=False)
    agg = df.groupby(["epsilon", "precommit"]).agg(
        coalition_utility=("coalition_utility", "mean"),
        advantage=("advantage_vs_honest", "mean"),
        advantage_pos_frac=("advantage_vs_honest", lambda x: float((x > 0).mean())),
    ).reset_index()
    print("Coalition outcome by epsilon and precommit:")
    print(agg.to_string(index=False))
    return df


if __name__ == "__main__":
    t0 = time.time()
    r1_v2_temperature_calibration()
    m5_v2_smoothness_100trial()
    r7_v2_coalition_corrected()
    print(f"\nIteration 2 done in {time.time()-t0:.1f}s")
