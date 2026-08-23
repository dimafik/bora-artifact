"""V31-V40: 10 LAC extension experiments.

V31: BFT integration (3-phase commit)
V32: Asynchronous + sharding combined
V33: Cross-chain bridge integration
V34: Validator rotation (committee membership change)
V35: Light client validation
V36: Stake delegation effects
V37: Encrypted state oracles
V38: Compression-aware scheduling
V39: Privacy-preserving aggregation
V40: Composability stress test
"""
from __future__ import annotations
import sys
import time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import numpy as np
import pandas as pd


def v31_bft_3phase():
    """3-phase commit cost analysis."""
    print("\n=== V31: BFT 3-phase commit ===\n")
    records = []
    for n_nodes in [4, 7, 13, 21]:
        for seed in range(5):
            rng = np.random.default_rng(seed + n_nodes)
            # 3 phases: prepare, commit, decide
            # Each phase = quorum round (2/3 + 1)
            quorum = (2 * n_nodes // 3) + 1
            n_rounds = 500
            total_latencies = []
            for t in range(n_rounds):
                # Each phase's latency = max RTT to quorum-th fastest node
                phase_lats = []
                for phase in range(3):
                    rtts = sorted(rng.exponential(1.0, size=n_nodes))
                    phase_lats.append(rtts[quorum-1])  # quorum-th fastest
                total_latencies.append(sum(phase_lats))
            records.append({
                "n_nodes": n_nodes,
                "seed": seed,
                "mean_total_latency": float(np.mean(total_latencies)),
                "p99_total_latency": float(np.percentile(total_latencies, 99)),
            })
    df = pd.DataFrame(records)
    out = Path(__file__).resolve().parent / "results" / "V31_bft_3phase.csv"
    df.to_csv(out, index=False)
    print(df.groupby("n_nodes").agg(latency_mean=("mean_total_latency", "mean"),
                                     latency_p99=("p99_total_latency", "mean")).to_string())
    return df


def v32_async_sharding():
    """Async + sharded blockchain combined."""
    print("\n=== V32: Async + Sharding ===\n")
    records = []
    for n_shards in [2, 4, 8, 16]:
        for seed in range(5):
            rng = np.random.default_rng(seed + n_shards)
            # Each shard processes tx independently; cross-shard tx requires both
            n_tx_per_shard = 500
            cross_shard_frac = 0.2
            misses = 0
            for tx in range(n_tx_per_shard * n_shards):
                if rng.random() < cross_shard_frac:
                    # Cross-shard: needs 2 shards to commit
                    # Async: heavy-tail latency
                    lat1 = rng.pareto(2.0) + 1
                    lat2 = rng.pareto(2.0) + 1
                    total = max(lat1, lat2)
                else:
                    total = rng.pareto(2.0) + 1
                if total > 10:
                    misses += 1
            records.append({
                "n_shards": n_shards,
                "seed": seed,
                "miss_rate": misses / (n_tx_per_shard * n_shards),
            })
    df = pd.DataFrame(records)
    out = Path(__file__).resolve().parent / "results" / "V32_async_shard.csv"
    df.to_csv(out, index=False)
    print(df.groupby("n_shards").agg(miss_mean=("miss_rate", "mean")).to_string())
    return df


def v33_cross_chain_bridge():
    """Cross-chain bridge with LAC-based path selection."""
    print("\n=== V33: Cross-Chain Bridge ===\n")
    records = []
    # 3 chains × LAC selects best path
    for n_chains in [2, 3, 5, 8]:
        for seed in range(5):
            rng = np.random.default_rng(seed + n_chains)
            n_tx = 1000
            random_lats = []
            lac_lats = []
            for tx in range(n_tx):
                # Each tx must pass through n_chains chains
                # LAC selects best route; random doesn't
                chain_lats = rng.exponential(1.0, size=(n_chains, 5))  # 5 paths per chain
                # Random: random path
                random_path = rng.integers(0, 5, size=n_chains)
                random_total = sum(chain_lats[c, random_path[c]] for c in range(n_chains))
                # LAC: best path per chain
                lac_total = sum(chain_lats[c].min() for c in range(n_chains))
                random_lats.append(random_total)
                lac_lats.append(lac_total)
            records.append({
                "n_chains": n_chains,
                "seed": seed,
                "random_mean": float(np.mean(random_lats)),
                "lac_mean": float(np.mean(lac_lats)),
                "improvement_pct": (np.mean(random_lats) - np.mean(lac_lats)) /
                                   max(np.mean(random_lats), 1e-9) * 100,
            })
    df = pd.DataFrame(records)
    out = Path(__file__).resolve().parent / "results" / "V33_cross_chain.csv"
    df.to_csv(out, index=False)
    print(df.groupby("n_chains").agg(improvement=("improvement_pct", "mean")).to_string())
    return df


def v34_validator_rotation():
    """Committee membership changes over time."""
    print("\n=== V34: Validator Rotation ===\n")
    records = []
    rotation_rates = [0.0, 0.01, 0.05, 0.1, 0.2]  # fraction rotated per epoch
    for rate in rotation_rates:
        for seed in range(5):
            rng = np.random.default_rng(seed + int(rate * 100))
            N = 11
            n_epochs = 50
            epoch_costs = []
            for epoch in range(n_epochs):
                # Rotate some validators
                n_rotate = int(N * rate)
                rotated = rng.choice(N, size=n_rotate, replace=False) if n_rotate > 0 else []
                # Per-validator base latency
                latencies = rng.exponential(1.0, size=N)
                latencies[rotated] *= 2.0  # new validators slower
                # Top-3 selection
                top_k = np.argsort(latencies)[:3]
                epoch_costs.append(float(np.min(latencies[top_k])))
            records.append({
                "rotation_rate": rate,
                "seed": seed,
                "mean_cost": float(np.mean(epoch_costs)),
            })
    df = pd.DataFrame(records)
    out = Path(__file__).resolve().parent / "results" / "V34_rotation.csv"
    df.to_csv(out, index=False)
    print(df.groupby("rotation_rate").agg(cost=("mean_cost", "mean")).to_string())
    return df


def v35_light_client():
    """Light client validation overhead."""
    print("\n=== V35: Light Client Validation ===\n")
    records = []
    for n_signatures in [1, 5, 10, 20, 50]:
        for seed in range(5):
            rng = np.random.default_rng(seed + n_signatures)
            n_blocks = 1000
            # Per-block signature verification time (μs)
            sig_time = 0.5 * n_signatures + rng.normal(0, 0.1, size=n_blocks)
            sig_time = np.maximum(0.01, sig_time)
            records.append({
                "n_signatures": n_signatures,
                "seed": seed,
                "mean_sig_time_us": float(np.mean(sig_time) * 1000),
                "throughput_blocks_per_s": float(1.0 / np.mean(sig_time)),
            })
    df = pd.DataFrame(records)
    out = Path(__file__).resolve().parent / "results" / "V35_light_client.csv"
    df.to_csv(out, index=False)
    print(df.groupby("n_signatures").agg(throughput=("throughput_blocks_per_s", "mean")).to_string())
    return df


def v36_stake_delegation():
    """Stake delegation impact on LAC."""
    print("\n=== V36: Stake Delegation ===\n")
    records = []
    delegation_fracs = [0.0, 0.2, 0.5, 0.8]  # fraction of stake delegated to top-3
    for frac in delegation_fracs:
        for seed in range(5):
            rng = np.random.default_rng(seed + int(frac * 100))
            N = 11
            n_rounds = 1000
            # Distribute stake: frac concentrated on top-3, rest distributed
            stakes = rng.exponential(1.0, size=N)
            sorted_idx = np.argsort(-stakes)
            stakes[sorted_idx[:3]] *= (1 + 3 * frac)
            stakes = stakes / stakes.sum()
            costs = []
            for t in range(n_rounds):
                rtt = rng.exponential(1.0, size=N)
                # Stake-weighted selection
                inv_rtt = 1.0 / np.maximum(rtt, 0.01)
                weighted = stakes * inv_rtt
                top_k = np.argsort(-weighted)[:3]
                costs.append(float(np.min(rtt[top_k])))
            records.append({
                "delegation_frac": frac,
                "seed": seed,
                "mean_cost": float(np.mean(costs)),
                "stake_gini": float(np.std(stakes)),
            })
    df = pd.DataFrame(records)
    out = Path(__file__).resolve().parent / "results" / "V36_delegation.csv"
    df.to_csv(out, index=False)
    print(df.groupby("delegation_frac").agg(cost=("mean_cost", "mean"),
                                              gini=("stake_gini", "mean")).to_string())
    return df


def v37_encrypted_oracle():
    """Encrypted state oracles (FHE overhead simulation)."""
    print("\n=== V37: Encrypted State Oracle (FHE) ===\n")
    records = []
    encryption_modes = ["plaintext", "lattice_he", "fhe_bgv", "fhe_ckks"]
    overhead = {"plaintext": 1, "lattice_he": 50, "fhe_bgv": 1000, "fhe_ckks": 500}
    for mode in encryption_modes:
        for seed in range(5):
            rng = np.random.default_rng(seed + hash(mode) % 1000)
            base_inference = 1.0  # ms
            mode_inference = base_inference * overhead[mode]
            records.append({
                "encryption_mode": mode,
                "seed": seed,
                "inference_ms": mode_inference + rng.normal(0, mode_inference * 0.1),
                "viable": int(mode_inference < 100),  # <100ms = real-time viable
            })
    df = pd.DataFrame(records)
    out = Path(__file__).resolve().parent / "results" / "V37_encrypted.csv"
    df.to_csv(out, index=False)
    print(df.groupby("encryption_mode").agg(inf_mean=("inference_ms", "mean"),
                                              viable=("viable", "mean")).to_string())
    return df


def v38_compression_aware():
    """Compression-aware scheduling (different message sizes)."""
    print("\n=== V38: Compression-Aware Scheduling ===\n")
    records = []
    compression_ratios = [1.0, 0.7, 0.5, 0.3]  # 1.0 = no compression
    for ratio in compression_ratios:
        for seed in range(5):
            rng = np.random.default_rng(seed + int(ratio * 100))
            n_rounds = 1000
            # Compression adds CPU but reduces network
            cpu_overhead = (1 - ratio) * 0.3  # ms
            network_time = ratio * 5.0  # ms
            costs = []
            for t in range(n_rounds):
                cost = cpu_overhead + network_time + rng.exponential(0.5)
                costs.append(cost)
            records.append({
                "compression_ratio": ratio,
                "seed": seed,
                "mean_total": float(np.mean(costs)),
            })
    df = pd.DataFrame(records)
    out = Path(__file__).resolve().parent / "results" / "V38_compression.csv"
    df.to_csv(out, index=False)
    print(df.groupby("compression_ratio").agg(cost=("mean_total", "mean")).to_string())
    return df


def v39_privacy_aggregation():
    """Privacy-preserving aggregation (multi-party computation)."""
    print("\n=== V39: Privacy-Preserving Aggregation ===\n")
    records = []
    mpc_modes = ["none", "secret_sharing", "garbled_circuit", "smpc"]
    overhead = {"none": 1, "secret_sharing": 5, "garbled_circuit": 30, "smpc": 100}
    for mode in mpc_modes:
        for seed in range(5):
            rng = np.random.default_rng(seed + hash(mode) % 1000)
            base = 2.0  # ms baseline aggregation
            mode_time = base * overhead[mode]
            records.append({
                "mpc_mode": mode,
                "seed": seed,
                "aggregation_ms": mode_time + rng.normal(0, mode_time * 0.05),
                "privacy_level": {"none": 0, "secret_sharing": 1,
                                  "garbled_circuit": 2, "smpc": 3}[mode],
            })
    df = pd.DataFrame(records)
    out = Path(__file__).resolve().parent / "results" / "V39_privacy.csv"
    df.to_csv(out, index=False)
    print(df.groupby("mpc_mode").agg(time=("aggregation_ms", "mean"),
                                       privacy=("privacy_level", "first")).to_string())
    return df


def v40_composability_stress():
    """Composability stress test: 5-layer LAC stack."""
    print("\n=== V40: Composability Stress Test ===\n")
    records = []
    n_layers_options = [1, 2, 3, 5, 10]
    for n_layers in n_layers_options:
        for seed in range(5):
            rng = np.random.default_rng(seed + n_layers)
            n_tx = 500
            # Each layer contributes alpha, beta degradation
            # Composition: alpha_total = product of alphas (Paper-5 result)
            alpha_per_layer = 1.1
            beta_per_layer = 1.05
            alpha_total = alpha_per_layer ** n_layers
            beta_total = max(beta_per_layer ** n_layers / n_layers, 1.0)
            # Latency: alpha_total × OPT
            base_lat = rng.exponential(1.0, size=n_tx)
            composed_lat = base_lat * alpha_total
            records.append({
                "n_layers": n_layers,
                "seed": seed,
                "alpha_total": alpha_total,
                "beta_total": beta_total,
                "mean_lat": float(np.mean(composed_lat)),
            })
    df = pd.DataFrame(records)
    out = Path(__file__).resolve().parent / "results" / "V40_composability.csv"
    df.to_csv(out, index=False)
    print(df.groupby("n_layers").agg(alpha=("alpha_total", "first"),
                                       beta=("beta_total", "first"),
                                       lat=("mean_lat", "mean")).to_string())
    return df


if __name__ == "__main__":
    t0 = time.time()
    v31_bft_3phase()
    v32_async_sharding()
    v33_cross_chain_bridge()
    v34_validator_rotation()
    v35_light_client()
    v36_stake_delegation()
    v37_encrypted_oracle()
    v38_compression_aware()
    v39_privacy_aggregation()
    v40_composability_stress()
    print(f"\nV31-V40 done in {time.time()-t0:.1f}s")
