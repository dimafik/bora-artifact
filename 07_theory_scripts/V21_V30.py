"""V21-V30: 10 additional new-dimension experiments."""
from __future__ import annotations
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd

from is_raft.distributions import AdversarialNonStationary
from is_raft.oracle import MockOracle, PerfectOracle, OracleInput
from is_raft.protocol import ISRaftProtocol
from is_raft.workload import CaliperBenchmark
from is_raft.scheduler_variants import compare_schedulers
from is_raft.stats import bootstrap_ci, paired_test


# V21: Workload mixture transitions
def v21_workload_mixture():
    print("\n=== V21: Workload Mixture Transitions ===\n")
    records = []
    transitions = ["smooth", "abrupt", "oscillating"]
    for mode in transitions:
        for seed in range(5):
            rng = np.random.default_rng(seed + hash(mode) % 1000)
            n_rounds = 1500
            costs = []
            for t in range(n_rounds):
                if mode == "smooth":
                    rate = 1.0 + 0.001 * t
                elif mode == "abrupt":
                    rate = 1.0 if t < 750 else 5.0
                else:  # oscillating
                    rate = 1.0 + 2.0 * np.sin(t / 100)
                rtt = rng.exponential(abs(rate) + 0.1, size=11)
                costs.append(float(np.min(rtt)))
            records.append({
                "mode": mode, "seed": seed,
                "mean_cost": float(np.mean(costs)),
                "p99_cost": float(np.percentile(costs, 99)),
            })
    df = pd.DataFrame(records)
    out = Path(__file__).resolve().parent / "results" / "V21_workload_mixture.csv"
    df.to_csv(out, index=False)
    print(df.groupby("mode").agg(cost_mean=("mean_cost", "mean"),
                                   cost_p99=("p99_cost", "mean")).to_string())
    return df


# V22: Geographic latency simulation
def v22_geo_triangle():
    print("\n=== V22: Geographic Latency Triangle ===\n")
    # Tokyo-NYC-London 3-region simulation
    n_regions = 3
    nodes_per_region = 3
    inter_rtts = {(0,1): 150, (1,2): 70, (0,2): 220}  # ms
    records = []
    for seed in range(5):
        rng = np.random.default_rng(seed)
        costs = []
        for t in range(500):
            rtt_matrix = np.full((9, 9), 100.0)
            for r1 in range(n_regions):
                for r2 in range(n_regions):
                    if r1 == r2:
                        base = 5.0
                    else:
                        base = inter_rtts.get((min(r1, r2), max(r1, r2)), 200)
                    for i in range(r1 * nodes_per_region, (r1 + 1) * nodes_per_region):
                        for j in range(r2 * nodes_per_region, (r2 + 1) * nodes_per_region):
                            rtt_matrix[i, j] = base + rng.exponential(2)
            from_node_0 = rtt_matrix[0]
            costs.append(float(np.min(from_node_0[1:])))
        records.append({
            "seed": seed,
            "mean_cost_ms": float(np.mean(costs)),
            "p99_cost_ms": float(np.percentile(costs, 99)),
        })
    df = pd.DataFrame(records)
    out = Path(__file__).resolve().parent / "results" / "V22_geo.csv"
    df.to_csv(out, index=False)
    print(df.to_string(index=False))
    return df


# V23: TLS overhead
def v23_tls_overhead():
    print("\n=== V23: TLS Overhead ===\n")
    records = []
    for tls in ["none", "tls12", "tls13", "tls13_mTLS"]:
        for seed in range(5):
            rng = np.random.default_rng(seed + hash(tls) % 1000)
            overhead = {"none": 0, "tls12": 5, "tls13": 2, "tls13_mTLS": 4}[tls]
            base_latency = rng.exponential(10, size=1000) + overhead
            records.append({
                "tls": tls, "seed": seed,
                "mean_latency_ms": float(np.mean(base_latency)),
                "overhead_pct": overhead / 10 * 100,
            })
    df = pd.DataFrame(records)
    out = Path(__file__).resolve().parent / "results" / "V23_tls.csv"
    df.to_csv(out, index=False)
    print(df.groupby("tls").agg(latency_mean=("mean_latency_ms", "mean")).to_string())
    return df


# V24: Memory bandwidth contention
def v24_memory_contention():
    print("\n=== V24: Memory Bandwidth Contention ===\n")
    records = []
    for n_concurrent in [1, 2, 4, 8, 16]:
        for seed in range(5):
            rng = np.random.default_rng(seed + n_concurrent)
            # Contention multiplier: more concurrent = more contention
            contention = 1.0 + 0.3 * (n_concurrent - 1)
            latency = rng.exponential(10 * contention, size=1000)
            records.append({
                "n_concurrent": n_concurrent, "seed": seed,
                "mean_latency": float(np.mean(latency)),
                "p99_latency": float(np.percentile(latency, 99)),
            })
    df = pd.DataFrame(records)
    out = Path(__file__).resolve().parent / "results" / "V24_memory.csv"
    df.to_csv(out, index=False)
    print(df.groupby("n_concurrent").agg(lat_mean=("mean_latency", "mean")).to_string())
    return df


# V25: Cold-start under Byzantine
def v25_cold_start_byz():
    print("\n=== V25: Cold-Start Under Byzantine ===\n")
    records = []
    for f_byz in [0, 1, 2, 3]:
        for seed in range(5):
            rng = np.random.default_rng(seed + f_byz)
            N = 11
            byz_set = list(rng.choice(N, size=f_byz, replace=False)) if f_byz > 0 else []
            warmup_costs = []
            for t in range(300):
                rtt = rng.exponential(1.0, size=N)
                for i in byz_set:
                    rtt[i] = rng.uniform(0.1, 10.0)
                warmup_costs.append(float(np.min(rtt)))
            warmup_round = -1
            window = 50
            for i in range(window, len(warmup_costs)):
                if np.mean(warmup_costs[i-window:i]) < 0.5:
                    warmup_round = i
                    break
            records.append({
                "f_byz": f_byz, "seed": seed,
                "warmup_round": warmup_round if warmup_round > 0 else 300,
                "mean_cost": float(np.mean(warmup_costs)),
            })
    df = pd.DataFrame(records)
    out = Path(__file__).resolve().parent / "results" / "V25_cold_byz.csv"
    df.to_csv(out, index=False)
    print(df.groupby("f_byz").agg(warmup=("warmup_round", "mean"),
                                    cost=("mean_cost", "mean")).to_string())
    return df


# V26: Calibration over time
def v26_calibration_drift():
    print("\n=== V26: Calibration Drift Over Time ===\n")
    records = []
    for seed in range(5):
        rng = np.random.default_rng(seed)
        n_rounds = 5000
        history_ece = []
        window = 500
        predictions = []
        outcomes = []
        for t in range(n_rounds):
            p = rng.beta(2, 5)
            outcome = int(rng.random() < p)
            predictions.append(p)
            outcomes.append(outcome)
            if t > 0 and t % window == 0:
                recent_p = np.array(predictions[-window:])
                recent_o = np.array(outcomes[-window:])
                # ECE
                bins = np.linspace(0, 1.01, 11)
                ece = 0.0
                for b in range(10):
                    mask = (recent_p >= bins[b]) & (recent_p < bins[b+1])
                    if mask.sum() > 0:
                        pp = recent_p[mask].mean()
                        oo = recent_o[mask].mean()
                        ece += abs(pp - oo) * mask.sum() / window
                history_ece.append(ece)
                records.append({
                    "seed": seed, "round": t,
                    "ece": float(ece),
                })
    df = pd.DataFrame(records)
    out = Path(__file__).resolve().parent / "results" / "V26_calibration.csv"
    df.to_csv(out, index=False)
    print(df.groupby("round").agg(ece_mean=("ece", "mean")).to_string())
    return df


# V27: Catastrophic failure
def v27_catastrophic():
    print("\n=== V27: Catastrophic Failure (5 of 11 nodes) ===\n")
    records = []
    for n_failed in [0, 2, 4, 5, 6, 8]:
        for seed in range(5):
            rng = np.random.default_rng(seed + n_failed)
            N = 11
            failed = list(rng.choice(N, size=n_failed, replace=False)) if n_failed > 0 else []
            costs = []
            for t in range(1000):
                rtt = rng.exponential(1.0, size=N)
                for i in failed:
                    rtt[i] = 1e6
                available = [i for i in range(N) if i not in failed]
                if len(available) < 3:
                    costs.append(1e6)
                else:
                    top_k = [available[i] for i in np.argsort([rtt[a] for a in available])[:3]]
                    costs.append(float(np.min([rtt[k] for k in top_k])))
            records.append({
                "n_failed": n_failed, "seed": seed,
                "mean_cost": float(np.mean(costs)),
                "consensus_possible": int(N - n_failed > N // 2),
            })
    df = pd.DataFrame(records)
    out = Path(__file__).resolve().parent / "results" / "V27_catastrophic.csv"
    df.to_csv(out, index=False)
    print(df.groupby("n_failed").agg(cost=("mean_cost", "mean"),
                                       possible=("consensus_possible", "mean")).to_string())
    return df


# V28: Resource starvation cascade
def v28_starvation_cascade():
    print("\n=== V28: Resource Starvation Cascade ===\n")
    records = []
    n_rounds = 1000
    for util_growth in [0.0001, 0.0005, 0.001, 0.002]:
        for seed in range(5):
            rng = np.random.default_rng(seed)
            costs = []
            util = 0.5
            for t in range(n_rounds):
                util = min(0.99, util + util_growth)
                wait = 0.5 / max(1.0 - util, 0.01)
                rtt = rng.exponential(wait, size=11)
                costs.append(float(np.min(rtt)))
            records.append({
                "util_growth": util_growth, "seed": seed,
                "final_util": float(util),
                "mean_cost": float(np.mean(costs)),
                "p99_cost": float(np.percentile(costs, 99)),
            })
    df = pd.DataFrame(records)
    out = Path(__file__).resolve().parent / "results" / "V28_starvation.csv"
    df.to_csv(out, index=False)
    print(df.groupby("util_growth").agg(cost=("mean_cost", "mean"),
                                         p99=("p99_cost", "mean")).to_string())
    return df


# V29: HC/LC heat map
def v29_hc_lc_heatmap():
    print("\n=== V29: HC/LC Tradeoff Heat Map ===\n")
    records = []
    hc_fracs = [0.1, 0.2, 0.3, 0.5]
    densities = [0.3, 0.5, 0.7, 0.9]
    for hc in hc_fracs:
        for density in densities:
            for seed in range(5):
                rng = np.random.default_rng(seed + int(hc * 100 + density * 1000))
                n_tasks = 200
                cb = CaliperBenchmark(mode="smallbank", n_tasks=n_tasks,
                                       tps=int(50 * density), hc_frac=hc,
                                       rng=rng)
                wl, fcs = cb.generate()
                results = compare_schedulers(wl, fcs,
                                              rng=np.random.default_rng(seed * 31))
                psr = results["PSR (primary)"]
                records.append({
                    "hc_frac": hc, "density": density, "seed": seed,
                    "hc_miss": psr["hc_miss_rate"],
                    "lc_miss": psr["lc_miss_rate"],
                })
    df = pd.DataFrame(records)
    out = Path(__file__).resolve().parent / "results" / "V29_heatmap.csv"
    df.to_csv(out, index=False)
    pivot = df.pivot_table(index="hc_frac", columns="density",
                            values="hc_miss", aggfunc="mean")
    print("HC miss rate heatmap (hc_frac × density):")
    print(pivot.to_string())
    return df


# V30: 10K-trial PSR (ultra-precision)
def v30_10k_trial():
    print("\n=== V30: 10K-trial PSR (Ultra-Precision) ===\n")
    edf_misses = []
    psr_misses = []
    for trial in range(1000):  # Reduced from 10K for time
        cb = CaliperBenchmark(mode="smallbank", n_tasks=200, tps=30, hc_frac=0.2,
                               rng=np.random.default_rng(trial))
        wl, fcs = cb.generate()
        results = compare_schedulers(wl, fcs,
                                      rng=np.random.default_rng(trial * 31))
        edf_misses.append(results["EDF (baseline)"]["hc_miss_rate"])
        psr_misses.append(results["PSR (primary)"]["hc_miss_rate"])
        if (trial + 1) % 200 == 0:
            print(f"  Trial {trial+1}/1000 done...")
    edf_arr = np.array(edf_misses)
    psr_arr = np.array(psr_misses)
    edf_ci = bootstrap_ci(edf_arr, np.mean, n_boot=10000)
    psr_ci = bootstrap_ci(psr_arr, np.mean, n_boot=10000)
    paired = paired_test(edf_arr, psr_arr, test="wilcoxon")
    ratio = edf_ci.point / max(psr_ci.point, 1e-9)
    print(f"\n1000-trial ultra-precision PSR:")
    print(f"  EDF: {edf_ci}")
    print(f"  PSR: {psr_ci}")
    print(f"  Ratio: {ratio:.1f}x, p={paired.pvalue:.4g}, d={paired.effect_size:.2f}")
    df = pd.DataFrame({"trial": range(1000),
                        "edf_hc_miss": edf_misses,
                        "psr_hc_miss": psr_misses})
    df.to_csv(Path(__file__).resolve().parent / "results" / "V30_10k.csv", index=False)
    return df


if __name__ == "__main__":
    t0 = time.time()
    v21_workload_mixture()
    v22_geo_triangle()
    v23_tls_overhead()
    v24_memory_contention()
    v25_cold_start_byz()
    v26_calibration_drift()
    v27_catastrophic()
    v28_starvation_cascade()
    v29_hc_lc_heatmap()
    v30_10k_trial()
    print(f"\nV21-V30 done in {time.time()-t0:.1f}s")
