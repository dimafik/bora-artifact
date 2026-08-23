"""
sim_v13_s2_ne2_dp_sweep.py - S2: NE2 model-extraction DP epsilon sweep.

Sweep epsilon in {0.01, 0.05, 0.1, 0.5, 1, 2, 5} to find where attacker
cos-similarity drops below 0.5 (random-guess level).
"""
from __future__ import annotations
import json
import numpy as np
from pathlib import Path
from sklearn.linear_model import LogisticRegression

rng = np.random.default_rng(20260604)

HERE = Path(__file__).parent
OUT = HERE / "s2_ne2_dp_sweep_results"
OUT.mkdir(parents=True, exist_ok=True)

TRUE_W = np.array([0.7, -0.3, 0.4, 0.1])
N_QUERIES = 500
EPS_VALUES = [0.01, 0.05, 0.1, 0.5, 1.0, 2.0, 5.0]
N_TRIALS = 30


def run_extraction(eps: float):
    cos_sims = []
    for _ in range(N_TRIALS):
        X = rng.normal(0, 1, (N_QUERIES, 4))
        true_logits = X @ TRUE_W
        true_decisions = (true_logits > 0).astype(float)
        if eps is None:
            noisy = true_decisions
        else:
            # Laplace mechanism on binary decision: flip with prob exp(-eps)/(1+exp(-eps))
            # Equivalent: add Lap(0, 1/eps) noise, threshold at 0.5
            noise = rng.laplace(0, 1.0 / eps, N_QUERIES)
            noisy = (true_decisions + noise > 0.5).astype(float)
        try:
            lr = LogisticRegression(C=1.0, max_iter=500)
            lr.fit(X, noisy)
            recovered = lr.coef_[0]
            cos = float(
                (TRUE_W @ recovered) /
                max(1e-9, np.linalg.norm(TRUE_W) * np.linalg.norm(recovered))
            )
        except Exception:
            cos = 0.0
        cos_sims.append(cos)
    return {
        "epsilon": eps if eps is not None else "no_defense",
        "cos_sim_mean": float(np.mean(cos_sims)),
        "cos_sim_std": float(np.std(cos_sims)),
        "n_trials": N_TRIALS,
    }


def main():
    results = [run_extraction(None)]  # no defense baseline
    for eps in EPS_VALUES:
        results.append(run_extraction(eps))

    # Find the epsilon where cos-sim falls below 0.5
    breakpoint_eps = None
    for r in results[1:]:
        if r["cos_sim_mean"] < 0.5:
            breakpoint_eps = r["epsilon"]
            break

    (OUT / "ne2_dp_sweep.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8")
    md = ["# NE2 (S2): Model-Extraction DP epsilon Sweep\n"]
    md.append(f"500 queries, {N_TRIALS} trials per epsilon, Laplace mechanism.\n")
    md.append("\n| epsilon | cos-sim mean | cos-sim std |")
    md.append("|---|---:|---:|")
    for r in results:
        md.append(f"| {r['epsilon']} | {r['cos_sim_mean']:.4f} | "
                  f"{r['cos_sim_std']:.4f} |")
    md.append("")
    md.append(f"**Breakpoint epsilon (cos-sim < 0.5)**: "
              f"{breakpoint_eps if breakpoint_eps else 'NONE in sweep range'}")
    (OUT / "REPORT.md").write_text("\n".join(md), encoding="utf-8")
    print(f"\n{(OUT/'REPORT.md').read_text(encoding='utf-8')}")


if __name__ == "__main__":
    main()
