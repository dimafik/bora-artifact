"""Tier1-B — Empirical Tail Index Measurement.

Fits Pareto/Generalized Pareto distribution to S-Raft EC2 RTT trace and
extracts tail index alpha. Provides quantitative ground-truth for Theorem 1's
heavy-tail assumption.

Outputs:
  - Per-trace tail index (Hill estimator, MLE)
  - 95% CI via bootstrap
  - Goodness-of-fit (KS test against Pareto)
  - Comparison vs log-normal alternative (AIC)
  - Density crossing analysis: where rho_crit = 1/sqrt(N) lies in workload space
"""
from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd
from scipy import stats
from typing import Optional

TRACE_DIR = Path(__file__).resolve().parents[3] / "두번째 논문" / "S_raft_SRDS" / "version2" / "results"


def hill_estimator(samples: np.ndarray, k_frac: float = 0.1) -> tuple[float, float]:
    """Hill estimator for tail index alpha.
    Returns (alpha_hat, std_err) using k = k_frac * n upper-order statistics.

    Hill's MLE: 1/alpha = (1/k) * sum_{i=1}^{k} log(X_(n-i+1) / X_(n-k))
    """
    x = np.sort(samples)[::-1]  # descending
    n = len(x)
    k = max(2, int(k_frac * n))
    log_ratios = np.log(x[:k] / x[k])
    inv_alpha = np.mean(log_ratios)
    alpha = 1.0 / inv_alpha if inv_alpha > 0 else float("inf")
    std_err = alpha / np.sqrt(k)  # asymptotic std
    return alpha, std_err


def bootstrap_hill(samples: np.ndarray, k_frac: float = 0.1,
                   n_boot: int = 1000, seed: int = 0) -> tuple[float, float, float]:
    """Bootstrap 95% CI for Hill estimator."""
    rng = np.random.default_rng(seed)
    alphas = []
    n = len(samples)
    for _ in range(n_boot):
        resample = rng.choice(samples, size=n, replace=True)
        a, _ = hill_estimator(resample, k_frac)
        if np.isfinite(a):
            alphas.append(a)
    alphas = np.array(alphas)
    return float(np.mean(alphas)), float(np.percentile(alphas, 2.5)), float(np.percentile(alphas, 97.5))


def ks_pareto_fit(samples: np.ndarray) -> tuple[float, float]:
    """Maximum-likelihood Pareto fit + Kolmogorov-Smirnov goodness of fit.
    Returns (alpha_mle, ks_pvalue).
    """
    x = samples[samples > 0]
    xm = x.min()
    alpha_mle = len(x) / np.sum(np.log(x / xm))
    ks_stat, pvalue = stats.kstest(x, lambda t: 1 - (xm / t) ** alpha_mle if (t >= xm).all() else 0)
    return float(alpha_mle), float(pvalue)


def aic_compare_pareto_vs_lognormal(samples: np.ndarray) -> dict:
    """Compare Pareto vs log-normal fit via AIC. Lower AIC = better."""
    x = samples[samples > 0]
    n = len(x)
    # Pareto MLE (2 params: xm, alpha)
    xm = x.min()
    alpha_p = n / np.sum(np.log(x / xm))
    log_lik_p = n * np.log(alpha_p) + n * alpha_p * np.log(xm) - (alpha_p + 1) * np.sum(np.log(x))
    aic_p = 2 * 2 - 2 * log_lik_p
    # Lognormal MLE (2 params: mu, sigma)
    log_x = np.log(x)
    mu_l, sigma_l = log_x.mean(), log_x.std(ddof=1)
    log_lik_l = -n / 2 * np.log(2 * np.pi) - n * np.log(sigma_l) - np.sum(log_x) - np.sum((log_x - mu_l) ** 2) / (2 * sigma_l ** 2)
    aic_l = 2 * 2 - 2 * log_lik_l
    return {
        "pareto_alpha": alpha_p,
        "pareto_logLik": log_lik_p,
        "pareto_AIC": aic_p,
        "lognormal_mu": mu_l,
        "lognormal_sigma": sigma_l,
        "lognormal_logLik": log_lik_l,
        "lognormal_AIC": aic_l,
        "delta_AIC_pareto_minus_lognormal": aic_p - aic_l,
        "best_fit": "pareto" if aic_p < aic_l else "lognormal",
    }


def extract_rtt_samples(trace_files: list, columns: list = None) -> dict:
    """Load latency samples from S-Raft CSV traces.
    Returns {trace_name: np.ndarray of latencies (ms)}."""
    columns = columns or ["mean", "p50", "p95", "p99"]
    out = {}
    for fname in trace_files:
        fp = TRACE_DIR / fname
        if not fp.exists():
            print(f"  [skip] {fname} not found")
            continue
        df = pd.read_csv(fp)
        samples = []
        for col in columns:
            if col in df.columns:
                samples.extend(df[col].dropna().values)
        if samples:
            out[fname.replace(".csv", "")] = np.array(samples, dtype=float)
    return out


def critical_density_threshold(N_values=(5, 7, 11, 15, 21)) -> pd.DataFrame:
    """rho_crit = 1/sqrt(N) — Theorem 1's density threshold across committee sizes."""
    return pd.DataFrame({
        "N": N_values,
        "rho_crit": [1.0 / np.sqrt(N) for N in N_values],
        "rho_crit_pct": [100.0 / np.sqrt(N) for N in N_values],
    })


if __name__ == "__main__":
    # Available S-Raft EC2 traces
    trace_files = [
        "v3_J1_jitter.csv", "v3_J2_jitter.csv", "v3_L_loss.csv",
        "phase_A_leader.csv", "phase_B_leader.csv", "phase_W_leader.csv",
        "v4_J1.csv", "v4_J2.csv", "v4_R.csv", "v4_D.csv",
    ]
    print(f"\n=== Tier1-B Empirical Tail Index Analysis ===")
    print(f"Trace dir: {TRACE_DIR}")
    samples = extract_rtt_samples(trace_files)
    print(f"Loaded {len(samples)} trace files\n")

    records = []
    for name, x in samples.items():
        if len(x) < 30:
            continue
        # Filter positive samples
        x = x[(x > 0) & np.isfinite(x)]
        if len(x) < 30:
            continue
        alpha_h, se_h = hill_estimator(x)
        alpha_boot_mean, ci_lo, ci_hi = bootstrap_hill(x)
        alpha_mle, ks_p = ks_pareto_fit(x)
        aic_res = aic_compare_pareto_vs_lognormal(x)
        records.append({
            "trace": name,
            "n_samples": len(x),
            "alpha_hill": alpha_h,
            "alpha_hill_se": se_h,
            "alpha_boot_mean": alpha_boot_mean,
            "alpha_boot_CI_lo": ci_lo,
            "alpha_boot_CI_hi": ci_hi,
            "alpha_mle": alpha_mle,
            "ks_pvalue": ks_p,
            "best_fit": aic_res["best_fit"],
            "delta_AIC": aic_res["delta_AIC_pareto_minus_lognormal"],
        })

    df = pd.DataFrame(records)
    out_dir = Path(__file__).resolve().parent / "results"
    out_dir.mkdir(exist_ok=True)
    df.to_csv(out_dir / "B_tail_index.csv", index=False)

    print("Per-trace tail index estimates:")
    print(df[["trace", "n_samples", "alpha_hill", "alpha_boot_CI_lo",
              "alpha_boot_CI_hi", "best_fit"]].to_string(index=False))

    # Summary
    valid = df[np.isfinite(df["alpha_hill"]) & (df["alpha_hill"] > 0)]
    if len(valid) > 0:
        print(f"\n=== Summary ===")
        print(f"Mean alpha_hill across traces : {valid['alpha_hill'].mean():.3f}")
        print(f"Median alpha_hill             : {valid['alpha_hill'].median():.3f}")
        print(f"Range                          : "
              f"[{valid['alpha_hill'].min():.3f}, {valid['alpha_hill'].max():.3f}]")
        n_pareto = (valid['best_fit'] == 'pareto').sum()
        print(f"Pareto better than lognormal  : {n_pareto}/{len(valid)} traces")
        n_heavy = (valid['alpha_hill'] < 2.0).sum()
        print(f"Heavy-tail (alpha < 2)         : {n_heavy}/{len(valid)} traces")

    # Critical density threshold
    print(f"\n=== Theorem 1 Critical Density rho_crit = 1/sqrt(N) ===")
    print(critical_density_threshold().to_string(index=False))
    print(f"\nSaved to {out_dir}")
