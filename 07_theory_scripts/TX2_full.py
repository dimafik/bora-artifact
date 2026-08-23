"""TX-2 full: Mode-switching latency distribution across many configurations."""
from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd

from experiments.TX2_mode_switch_latency import (make_burst_workload,
                                                  simulate_with_mode_tracking)
from is_raft.stats import bootstrap_ci, paired_test


def run_tx2_full(n_trials: int = 50,
                  config_variants=None,
                  seed: int = 0):
    """50 trials × multiple workload configurations."""
    if config_variants is None:
        config_variants = [
            ("light_burst",  dict(n_lc_pre=20, n_hc_burst=10, n_lc_post=20,
                                  lc_arrival_rate=0.5, hc_burst_at=5.0)),
            ("medium_burst", dict(n_lc_pre=30, n_hc_burst=20, n_lc_post=30,
                                  lc_arrival_rate=0.8, hc_burst_at=10.0)),
            ("heavy_burst",  dict(n_lc_pre=40, n_hc_burst=30, n_lc_post=40,
                                  lc_arrival_rate=1.0, hc_burst_at=15.0)),
        ]

    all_records = []
    miss_records = []

    for cfg_name, cfg in config_variants:
        for trial in range(n_trials):
            rng = np.random.default_rng(seed + trial * 7919)
            wl, fcs = make_burst_workload(rng=rng, **cfg)
            for mode in ("MC", "EDF", "FIFO"):
                sim_rng = np.random.default_rng(seed + trial * 31)
                res = simulate_with_mode_tracking(wl, fcs, sim_rng, mode)
                for tr in res["transitions"]:
                    all_records.append({
                        "config": cfg_name,
                        "trial": trial,
                        "scheduler": mode,
                        "latency_ms": tr["latency_ms"],
                    })
                miss_records.append({
                    "config": cfg_name,
                    "trial": trial,
                    "scheduler": mode,
                    "n_transitions": res["n_transitions"],
                    "hc_miss": res["hc_miss"],
                    "lc_miss": res["lc_miss"],
                })

    trans_df = pd.DataFrame(all_records)
    miss_df = pd.DataFrame(miss_records)

    print("\n=== TX-2 FULL: Mode-Switch Transition Latency ===\n")
    # Per-config × mode latency summary
    summary = []
    for cfg_name, _ in config_variants:
        sub = trans_df[(trans_df["config"] == cfg_name) &
                       (trans_df["scheduler"] == "MC")]
        if len(sub) > 0:
            arr = sub["latency_ms"].values
            ci = bootstrap_ci(arr, np.mean, n_boot=2000)
            summary.append({
                "config": cfg_name,
                "n_transitions": len(arr),
                "mean_ms": ci.point,
                "ci_lo": ci.ci_lo,
                "ci_hi": ci.ci_hi,
                "p50_ms": float(np.percentile(arr, 50)),
                "p95_ms": float(np.percentile(arr, 95)),
                "p99_ms": float(np.percentile(arr, 99)),
                "p999_ms": float(np.percentile(arr, 99.9)),
            })
    summary_df = pd.DataFrame(summary)
    print("Mode-switch transition latency by config (MC only):")
    print(summary_df.to_string(index=False))

    print("\nMiss rate comparison (MC vs EDF):")
    agg = miss_df.groupby(["config", "scheduler"]).agg(
        hc_miss_mean=("hc_miss", "mean"),
        lc_miss_mean=("lc_miss", "mean"),
        transitions=("n_transitions", "mean"),
    ).reset_index()
    print(agg.to_string(index=False))

    # Statistical test: MC HC misses vs EDF HC misses (paired by trial)
    print("\nPaired Wilcoxon: HC miss rate, MC vs EDF (per config):")
    for cfg_name, _ in config_variants:
        mc_hc = miss_df[(miss_df["config"] == cfg_name) &
                        (miss_df["scheduler"] == "MC")]["hc_miss"].values
        edf_hc = miss_df[(miss_df["config"] == cfg_name) &
                         (miss_df["scheduler"] == "EDF")]["hc_miss"].values
        if len(mc_hc) == len(edf_hc):
            tr = paired_test(mc_hc, edf_hc, test="wilcoxon")
            print(f"  {cfg_name}: stat={tr.statistic:.2f}, p={tr.pvalue:.4f}, "
                  f"cohen_d={tr.effect_size:.3f}, sig={tr.significant}")

    out_dir = Path(__file__).resolve().parent / "results"
    out_dir.mkdir(exist_ok=True)
    summary_df.to_csv(out_dir / "TX2_full_summary.csv", index=False)
    trans_df.to_csv(out_dir / "TX2_full_transitions.csv", index=False)
    miss_df.to_csv(out_dir / "TX2_full_misses.csv", index=False)
    return summary_df, trans_df, miss_df


if __name__ == "__main__":
    run_tx2_full()
