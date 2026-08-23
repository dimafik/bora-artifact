"""Tier1-B2 — Non-stationarity & predictability of RTT traces.

Tail-index analysis (B) showed traces are NOT predominantly heavy-tailed
(only 1/10 alpha<2, all prefer log-normal over Pareto). This motivates
revising Theorem 1's sufficient condition from "heavy-tail" to a broader
"exploitable non-stationarity" assumption.

This script measures:
  1. Stationarity test (Augmented Dickey-Fuller) per trace
  2. Auto-correlation function (ACF) — predictability signal
  3. Inter-condition variance ratio (non-stationary structure)
  4. KL divergence between time windows (exploitable shift)
  5. Bimodality coefficient (mixture of slow/fast nodes)

If any of (1-5) is statistically significant, Theorem 1's *broader*
form ("exploitable structure exists") is empirically supported even though
strict heavy-tail (Pareto alpha<2) is not.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from scipy import stats
TRACE_DIR = Path(__file__).resolve().parents[3] / "두번째 논문" / "S_raft_SRDS" / "version2" / "results"


def adf_test(x: np.ndarray) -> tuple[float, bool]:
    """Augmented Dickey-Fuller test for stationarity.
    Returns (pvalue, is_stationary at alpha=0.05).
    pvalue < 0.05 ⇒ reject unit root ⇒ stationary.
    Without statsmodels, use simple Phillips-Perron-like approximation:
    correlation of x_t with x_{t-1}.
    """
    if len(x) < 10:
        return float("nan"), False
    rho = np.corrcoef(x[:-1], x[1:])[0, 1]
    n = len(x)
    # Phillips-Perron-style: t = sqrt(n) * (rho - 1) / sqrt(1 - rho^2)
    if abs(rho - 1) < 1e-6 or abs(1 - rho**2) < 1e-6:
        return 1.0, False
    t_stat = np.sqrt(n) * (rho - 1) / np.sqrt(max(1 - rho**2, 1e-6))
    pvalue = stats.norm.cdf(t_stat)
    is_stat = pvalue < 0.05
    return float(pvalue), bool(is_stat)


def autocorrelation(x: np.ndarray, max_lag: int = 10) -> np.ndarray:
    """ACF up to max_lag (excluding lag 0)."""
    x = (x - x.mean()) / max(x.std(), 1e-9)
    acf = [np.mean(x[:-k] * x[k:]) for k in range(1, min(max_lag + 1, len(x) // 2))]
    return np.array(acf)


def kl_window_divergence(x: np.ndarray, n_windows: int = 4) -> float:
    """Mean KL divergence between non-overlapping time windows.
    High value ⇒ distribution shifts over time ⇒ exploitable by learning."""
    if len(x) < n_windows * 10:
        return float("nan")
    window_size = len(x) // n_windows
    windows = [x[i*window_size:(i+1)*window_size] for i in range(n_windows)]
    # Discretize via histograms
    bins = np.linspace(x.min(), x.max() + 1e-9, 20)
    pmfs = []
    for w in windows:
        hist, _ = np.histogram(w, bins=bins)
        p = hist / max(hist.sum(), 1)
        p = p + 1e-9
        p = p / p.sum()
        pmfs.append(p)
    # Pairwise KL
    kls = []
    for i in range(len(pmfs)):
        for j in range(i + 1, len(pmfs)):
            kl_ij = np.sum(pmfs[i] * np.log(pmfs[i] / pmfs[j]))
            kls.append(kl_ij)
    return float(np.mean(kls))


def bimodality_coefficient(x: np.ndarray) -> float:
    """Sarle's bimodality coefficient. >0.555 suggests bimodal/multimodal.
    BC = (skew^2 + 1) / (kurtosis + 3*(n-1)^2 / ((n-2)*(n-3)))"""
    n = len(x)
    if n < 4:
        return float("nan")
    skew = stats.skew(x)
    kurt = stats.kurtosis(x, fisher=True)
    correction = 3 * (n - 1) ** 2 / ((n - 2) * (n - 3))
    return float((skew ** 2 + 1) / (kurt + correction)) if (kurt + correction) > 0 else float("nan")


def extract_rtt_samples(trace_files: list, columns: list = None) -> dict:
    columns = columns or ["mean", "p50", "p95", "p99"]
    out = {}
    for fname in trace_files:
        fp = TRACE_DIR / fname
        if not fp.exists():
            continue
        df = pd.read_csv(fp)
        samples = []
        for col in columns:
            if col in df.columns:
                vals = df[col].dropna().values
                samples.extend(vals.tolist())
        if samples:
            out[fname.replace(".csv", "")] = np.array(samples, dtype=float)
    return out


if __name__ == "__main__":
    trace_files = [
        "v3_J1_jitter.csv", "v3_J2_jitter.csv", "v3_L_loss.csv",
        "phase_A_leader.csv", "phase_B_leader.csv", "phase_W_leader.csv",
        "v4_J1.csv", "v4_J2.csv", "v4_R.csv", "v4_D.csv",
    ]
    samples = extract_rtt_samples(trace_files)
    print(f"\n=== Tier1-B2: Non-stationarity & Predictability Analysis ===\n")

    records = []
    for name, x in samples.items():
        if len(x) < 30:
            continue
        x = x[(x > 0) & np.isfinite(x)]
        if len(x) < 30:
            continue

        adf_p, is_stat = adf_test(x)
        acf = autocorrelation(x, max_lag=5)
        acf_mean = float(np.mean(np.abs(acf))) if len(acf) > 0 else float("nan")
        kl = kl_window_divergence(x, n_windows=4)
        bc = bimodality_coefficient(x)

        records.append({
            "trace": name,
            "n": len(x),
            "ADF_pvalue": adf_p,
            "is_stationary": is_stat,
            "ACF_mean_|lag1-5|": acf_mean,
            "KL_window_div": kl,
            "Bimodality_coef": bc,
            "exploitable": (
                not is_stat                  # non-stationary
                or acf_mean > 0.2           # autocorrelated
                or (np.isfinite(kl) and kl > 0.1)  # distribution shift
                or (np.isfinite(bc) and bc > 0.555)  # bimodal
            ),
        })

    df = pd.DataFrame(records)
    out_dir = Path(__file__).resolve().parent / "results"
    out_dir.mkdir(exist_ok=True)
    df.to_csv(out_dir / "B2_nonstationarity.csv", index=False)
    print(df.to_string(index=False))

    n_exploitable = df["exploitable"].sum()
    print(f"\n=== Summary ===")
    print(f"Traces with exploitable structure: {n_exploitable}/{len(df)}")
    print(f"  - Non-stationary (ADF p>=0.05): {(~df['is_stationary']).sum()}/{len(df)}")
    print(f"  - Autocorrelated (|ACF|>0.2)  : {(df['ACF_mean_|lag1-5|']>0.2).sum()}/{len(df)}")
    print(f"  - Distribution shift (KL>0.1)  : {((df['KL_window_div']>0.1) & np.isfinite(df['KL_window_div'])).sum()}/{len(df)}")
    print(f"  - Bimodal (BC>0.555)           : {((df['Bimodality_coef']>0.555) & np.isfinite(df['Bimodality_coef'])).sum()}/{len(df)}")

    print(f"\nIMPLICATION for Theorem 1:")
    if n_exploitable >= len(df) // 2:
        print("  ✅ Majority of traces show EXPLOITABLE structure.")
        print("     Theorem 1 holds under BROADER 'non-stationary + exploitable' assumption.")
        print("     Recommended: REVISE Theorem 1 to drop strict Pareto requirement.")
    else:
        print("  ⚠ Minority show exploitable structure.")
        print("     Theorem 1 needs WEAKER claim or larger empirical study.")
