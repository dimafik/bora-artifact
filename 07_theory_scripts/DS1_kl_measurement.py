"""DS-1: Information-theoretic τ measurement on production traces.

Computes KL(D_t || D_{t-K}) on EC2 traces to empirically establish the
(τ, K)-exploitability parameter of Theorem 1.

Produces:
  - Per-trace τ distribution (histogram of KL divergences over sliding windows)
  - Average τ vs lag K curve
  - Empirical CDF showing fraction of windows exceeding various τ thresholds

This validates Theorem 1's premise on real production data.
"""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd
from scipy import stats

TRACE_DIR = Path(__file__).resolve().parents[3] / "두번째 논문" / "S_raft_SRDS" / "version2" / "results"


def empirical_kl(p_samples: np.ndarray, q_samples: np.ndarray,
                  n_bins: int = 20) -> float:
    """KL(P || Q) estimated via histograms with smoothing."""
    lo = min(float(p_samples.min()), float(q_samples.min()))
    hi = max(float(p_samples.max()), float(q_samples.max()))
    if hi <= lo:
        return 0.0
    bins = np.linspace(lo, hi + 1e-9, n_bins + 1)
    p_hist, _ = np.histogram(p_samples, bins=bins)
    q_hist, _ = np.histogram(q_samples, bins=bins)
    p = p_hist / max(p_hist.sum(), 1)
    q = q_hist / max(q_hist.sum(), 1)
    # Smooth zeros
    eps = 1e-9
    p = p + eps; p = p / p.sum()
    q = q + eps; q = q / q.sum()
    return float(np.sum(p * np.log(p / q)))


def compute_window_kl(samples: np.ndarray, window: int,
                       K_values=(1, 2, 5, 10, 20)) -> dict:
    """KL(D_t || D_{t-K}) for various K, over sliding windows of size `window`."""
    n = len(samples)
    if n < 2 * window:
        return {K: [] for K in K_values}
    kl_by_K = {K: [] for K in K_values}
    for t_end in range(window, n - max(K_values)):
        p_window = samples[t_end - window:t_end]
        for K in K_values:
            if t_end - K - window >= 0:
                q_window = samples[t_end - K - window:t_end - K]
                kl_by_K[K].append(empirical_kl(p_window, q_window))
    return kl_by_K


def extract_rtt_samples(trace_files: list,
                         columns: list = None) -> dict:
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
                samples.extend(df[col].dropna().values.tolist())
        if samples:
            out[fname.replace(".csv", "")] = np.array(samples, dtype=float)
    return out


def run_ds1(mode: str = "pilot"):
    if mode == "pilot":
        trace_files = ["v3_J1_jitter.csv", "phase_A_leader.csv"]
        K_values = (1, 5, 10)
    else:
        trace_files = ["v3_J1_jitter.csv", "v3_J2_jitter.csv", "v3_L_loss.csv",
                       "phase_A_leader.csv", "phase_B_leader.csv", "phase_W_leader.csv",
                       "v4_J1.csv", "v4_J2.csv", "v4_R.csv", "v4_D.csv"]
        K_values = (1, 2, 5, 10, 20)
    samples_dict = extract_rtt_samples(trace_files)
    records = []
    for name, samples in samples_dict.items():
        if len(samples) < 20:
            continue
        # Use windows of 10 samples
        window = max(5, len(samples) // 8)
        kl_by_K = compute_window_kl(samples, window=window, K_values=K_values)
        for K, kl_values in kl_by_K.items():
            if not kl_values:
                continue
            arr = np.array(kl_values)
            records.append({
                "trace": name,
                "n_samples": len(samples),
                "window": window,
                "K": K,
                "n_windows": len(kl_values),
                "tau_mean": float(arr.mean()),
                "tau_median": float(np.median(arr)),
                "tau_p95": float(np.percentile(arr, 95)),
                "tau_min": float(arr.min()),
                "tau_max": float(arr.max()),
                "frac_exceed_0.01": float(np.mean(arr > 0.01)),
                "frac_exceed_0.1": float(np.mean(arr > 0.1)),
                "frac_exceed_0.5": float(np.mean(arr > 0.5)),
                "frac_exceed_1.0": float(np.mean(arr > 1.0)),
                "exploitable": bool((arr.mean() > 0.01)),  # Thm 1 premise
            })
    return pd.DataFrame(records)


if __name__ == "__main__":
    import sys as _sys
    mode = _sys.argv[1] if len(_sys.argv) > 1 else "pilot"
    print(f"\n=== DS-1: Information-theoretic tau measurement ({mode}) ===\n")
    df = run_ds1(mode)
    out = Path(__file__).resolve().parent / "results" / f"DS1_{mode}.csv"
    out.parent.mkdir(exist_ok=True)
    df.to_csv(out, index=False)

    if len(df) == 0:
        print("No data; check trace paths")
    else:
        for K in sorted(df["K"].unique()):
            sub = df[df["K"] == K]
            print(f"K={K}:")
            for _, row in sub.iterrows():
                print(f"  {row['trace']:<20s} n={row['n_samples']:>4d}  "
                      f"tau_mean={row['tau_mean']:.3f}  "
                      f"tau_p95={row['tau_p95']:.3f}  "
                      f"frac>0.1={row['frac_exceed_0.1']:.2f}  "
                      f"exploitable={row['exploitable']}")
        n_exploitable = df.groupby("trace")["exploitable"].any().sum()
        n_traces = df["trace"].nunique()
        print(f"\n{n_exploitable}/{n_traces} traces show exploitable structure (Thm 1 premise)")
    print(f"\nSaved to {out}")
