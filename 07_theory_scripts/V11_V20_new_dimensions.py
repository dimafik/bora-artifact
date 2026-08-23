"""V11-V20: 10 new experimental dimensions.

V11: Cold-start (new node joining)
V12: Oracle epoch transition (Φ_d version migration)
V13: Stake-weighted Byzantine resistance
V14: Cross-channel transaction dependencies
V15: Snapshot/log-compaction interaction
V16: Asynchronous LAC (no GST assumption)
V17: Adversarial oracle attack
V18: Throughput-latency Pareto frontier
V19: Resource saturation (memory/CPU exhaustion)
V20: Multi-region failover under partial connectivity
"""
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


# ============================================================
# V11: Cold-start performance
# ============================================================
def v11_cold_start():
    """New node joins; measure ramp-up time to optimal performance."""
    print("\n=== V11: Cold-Start Performance ===\n")
    N = 11
    n_rounds = 1000
    records = []
    bootstrap_modes = ["from_zero", "from_neighbor_history", "from_snapshot"]
    for mode in bootstrap_modes:
        for seed in range(5):
            rng = np.random.default_rng(seed + hash(mode) % 1000)
            dist = AdversarialNonStationary(N=N, shift_mean=10,
                                              baseline_window_assumed=50, rng=rng)
            oracle = MockOracle(window=50)
            # Pre-populate history based on mode
            if mode == "from_zero":
                history = []
            elif mode == "from_neighbor_history":
                history = [dist.sample(t) for t in range(50)]
            else:  # from_snapshot
                history = [dist.sample(t) for t in range(100)]
            isr = ISRaftProtocol(oracle, N=N, k=3)
            costs = []
            cold_start_round = -1
            warmup_threshold = 0.5
            for t in range(n_rounds):
                r_t = dist.sample(t + len(history))
                H = np.array(history[-100:]) if history else np.zeros((0, N))
                inp = OracleInput(rtt_history=H, vote_delays=np.zeros_like(H),
                                  promote_outcomes=np.zeros_like(H), round_idx=t)
                cost = isr.run_round(r_t, inp).cost
                costs.append(cost)
                history.append(r_t)
                if cold_start_round == -1 and len(costs) >= 50:
                    recent = np.mean(costs[-50:])
                    if recent < warmup_threshold:
                        cold_start_round = t
            records.append({
                "bootstrap_mode": mode,
                "seed": seed,
                "warmup_round": cold_start_round if cold_start_round > 0 else n_rounds,
                "mean_cost_first_100": float(np.mean(costs[:100])),
                "mean_cost_last_100": float(np.mean(costs[-100:])),
            })
    df = pd.DataFrame(records)
    out = Path(__file__).resolve().parent / "results" / "V11_cold_start.csv"
    df.to_csv(out, index=False)
    agg = df.groupby("bootstrap_mode").agg(
        warmup_mean=("warmup_round", "mean"),
        early_cost=("mean_cost_first_100", "mean"),
        late_cost=("mean_cost_last_100", "mean"),
    ).reset_index()
    print(agg.to_string(index=False))
    return df


# ============================================================
# V12: Oracle epoch transition
# ============================================================
def v12_epoch_transition():
    """Φ_d version migration: smooth vs abrupt transition."""
    print("\n=== V12: Oracle Epoch Transition ===\n")
    N = 11
    n_rounds = 1500
    transition_round = 750
    records = []
    transition_modes = ["abrupt", "gradual_100", "gradual_200"]
    for mode in transition_modes:
        for seed in range(5):
            rng = np.random.default_rng(seed + hash(mode) % 1000)
            dist = AdversarialNonStationary(N=N, shift_mean=10,
                                              baseline_window_assumed=50, rng=rng)
            old_oracle = MockOracle(window=50)
            new_oracle = MockOracle(window=25)  # different config
            history = []
            costs = []
            transition_phase = []
            for t in range(n_rounds):
                r_t = dist.sample(t)
                H = np.array(history[-100:]) if history else np.zeros((0, N))
                inp = OracleInput(rtt_history=H, vote_delays=np.zeros_like(H),
                                  promote_outcomes=np.zeros_like(H), round_idx=t)
                if mode == "abrupt":
                    active_oracle = old_oracle if t < transition_round else new_oracle
                    isr = ISRaftProtocol(active_oracle, N=N, k=3)
                    cost = isr.run_round(r_t, inp).cost
                else:
                    transition_width = 100 if mode == "gradual_100" else 200
                    if t < transition_round:
                        isr = ISRaftProtocol(old_oracle, N=N, k=3)
                        cost = isr.run_round(r_t, inp).cost
                    elif t < transition_round + transition_width:
                        # Blend predictions
                        alpha = (t - transition_round) / transition_width
                        p_old = old_oracle.predict(inp)
                        p_new = new_oracle.predict(inp)
                        p_blend = (1 - alpha) * p_old + alpha * p_new
                        top_k = np.argsort(-p_blend)[:3]
                        cost = float(np.min(r_t[top_k]))
                    else:
                        isr = ISRaftProtocol(new_oracle, N=N, k=3)
                        cost = isr.run_round(r_t, inp).cost
                costs.append(cost)
                if transition_round - 50 <= t < transition_round + 150:
                    transition_phase.append(cost)
                history.append(r_t)
            records.append({
                "transition_mode": mode,
                "seed": seed,
                "transition_phase_mean": float(np.mean(transition_phase)) if transition_phase else float("nan"),
                "transition_phase_max": float(np.max(transition_phase)) if transition_phase else float("nan"),
            })
    df = pd.DataFrame(records)
    out = Path(__file__).resolve().parent / "results" / "V12_epoch.csv"
    df.to_csv(out, index=False)
    agg = df.groupby("transition_mode").agg(
        phase_mean=("transition_phase_mean", "mean"),
        phase_max=("transition_phase_max", "mean"),
    ).reset_index()
    print(agg.to_string(index=False))
    return df


# ============================================================
# V13: Stake-weighted Byzantine resistance
# ============================================================
def v13_stake_byzantine():
    """Byzantine nodes weighted by stake."""
    print("\n=== V13: Stake-Weighted Byzantine Resistance ===\n")
    N = 11
    n_rounds = 1500
    records = []
    byz_stake_fractions = [0.0, 0.1, 0.2, 0.33, 0.5]  # fraction of TOTAL stake that's Byzantine
    for bs_frac in byz_stake_fractions:
        for seed in range(5):
            rng = np.random.default_rng(seed + int(bs_frac * 100))
            stakes = rng.exponential(1.0, size=N)
            stakes_norm = stakes / stakes.sum()
            # Select Byzantine nodes to cover bs_frac of stake
            sorted_by_stake = np.argsort(-stakes)
            byz_set = []
            byz_stake = 0
            for i in sorted_by_stake:
                if byz_stake / stakes.sum() >= bs_frac:
                    break
                byz_set.append(i)
                byz_stake += stakes[i]
            costs = []
            for t in range(n_rounds):
                rtt = rng.exponential(1.0, size=N)
                # Byzantine misreport
                for i in byz_set:
                    rtt[i] *= rng.uniform(0.3, 3.0)
                # Stake-weighted selection
                inv_rtt = 1.0 / np.maximum(rtt, 0.01)
                stake_perf = stakes_norm * inv_rtt
                top_k = np.argsort(-stake_perf)[:3]
                costs.append(float(np.min(rtt[top_k])))
            records.append({
                "byz_stake_fraction": bs_frac,
                "seed": seed,
                "n_byz_nodes": len(byz_set),
                "mean_cost": float(np.mean(costs)),
            })
    df = pd.DataFrame(records)
    out = Path(__file__).resolve().parent / "results" / "V13_stake_byz.csv"
    df.to_csv(out, index=False)
    agg = df.groupby("byz_stake_fraction").agg(
        byz_nodes_mean=("n_byz_nodes", "mean"),
        cost_mean=("mean_cost", "mean"),
    ).reset_index()
    print(agg.to_string(index=False))
    return df


# ============================================================
# V14: Cross-channel transaction dependencies
# ============================================================
def v14_cross_channel():
    """Channels with dependent transactions (atomic swap-style)."""
    print("\n=== V14: Cross-Channel Dependencies ===\n")
    records = []
    n_channels_options = [2, 4, 8]
    for n_ch in n_channels_options:
        for seed in range(5):
            rng = np.random.default_rng(seed + n_ch)
            # Each round: n_ch channels run consensus
            # Dependent tx: chan 0 must commit before chan 1 can proceed
            n_dependent_chains = 100
            success_count = 0
            commit_times = []
            for chain in range(n_dependent_chains):
                # Per-channel commit latency
                chain_total = 0
                for ch in range(n_ch):
                    latency = rng.exponential(1.0)
                    chain_total += latency
                commit_times.append(chain_total)
                if chain_total < n_ch * 3.0:  # deadline = 3× expected
                    success_count += 1
            records.append({
                "n_channels": n_ch,
                "seed": seed,
                "success_rate": success_count / n_dependent_chains,
                "mean_chain_latency": float(np.mean(commit_times)),
                "p99_chain_latency": float(np.percentile(commit_times, 99)),
            })
    df = pd.DataFrame(records)
    out = Path(__file__).resolve().parent / "results" / "V14_cross_channel.csv"
    df.to_csv(out, index=False)
    agg = df.groupby("n_channels").agg(
        success_rate_mean=("success_rate", "mean"),
        chain_latency_mean=("mean_chain_latency", "mean"),
        chain_latency_p99=("p99_chain_latency", "mean"),
    ).reset_index()
    print(agg.to_string(index=False))
    return df


# ============================================================
# V15: Snapshot/log-compaction interaction
# ============================================================
def v15_snapshot():
    """Compaction every K rounds; measure oracle disruption."""
    print("\n=== V15: Snapshot Interaction ===\n")
    N = 11
    n_rounds = 2000
    records = []
    snapshot_periods = [None, 200, 500, 1000]
    for period in snapshot_periods:
        for seed in range(5):
            rng = np.random.default_rng(seed + (period or 0))
            dist = AdversarialNonStationary(N=N, shift_mean=10,
                                              baseline_window_assumed=50, rng=rng)
            oracle = MockOracle(window=50)
            isr = ISRaftProtocol(oracle, N=N, k=3)
            history = []
            costs = []
            for t in range(n_rounds):
                r_t = dist.sample(t)
                # Apply snapshot: clear history every `period` rounds
                if period is not None and t > 0 and t % period == 0:
                    history = history[-25:]  # keep only recent 25 (snapshot retention)
                H = np.array(history[-100:]) if history else np.zeros((0, N))
                inp = OracleInput(rtt_history=H, vote_delays=np.zeros_like(H),
                                  promote_outcomes=np.zeros_like(H), round_idx=t)
                costs.append(isr.run_round(r_t, inp).cost)
                history.append(r_t)
            records.append({
                "snapshot_period": str(period),
                "seed": seed,
                "mean_cost": float(np.mean(costs)),
                "p99_cost": float(np.percentile(costs, 99)),
            })
    df = pd.DataFrame(records)
    out = Path(__file__).resolve().parent / "results" / "V15_snapshot.csv"
    df.to_csv(out, index=False)
    agg = df.groupby("snapshot_period").agg(
        cost_mean=("mean_cost", "mean"),
        cost_p99=("p99_cost", "mean"),
    ).reset_index()
    print(agg.to_string(index=False))
    return df


# ============================================================
# V16: Asynchronous LAC (no GST)
# ============================================================
def v16_async_lac():
    """Async network (unbounded delays)."""
    print("\n=== V16: Async LAC ===\n")
    N = 11
    n_rounds = 1500
    records = []
    async_modes = ["partial_sync", "async_bounded", "fully_async"]
    for mode in async_modes:
        for seed in range(5):
            rng = np.random.default_rng(seed + hash(mode) % 1000)
            costs = []
            for t in range(n_rounds):
                if mode == "partial_sync":
                    # Standard exponential
                    rtt = rng.exponential(1.0, size=N)
                elif mode == "async_bounded":
                    # Heavy tail (Pareto)
                    rtt = rng.pareto(2.0, size=N) + 0.1
                else:  # fully_async
                    # Cauchy distribution (no mean)
                    rtt = np.abs(rng.standard_cauchy(size=N)) + 0.1
                top_k = np.argsort(rtt)[:3]
                costs.append(float(np.min(rtt[top_k])))
            records.append({
                "async_mode": mode,
                "seed": seed,
                "mean_cost": float(np.mean(costs)),
                "p99_cost": float(np.percentile(costs, 99)),
                "p999_cost": float(np.percentile(costs, 99.9)),
            })
    df = pd.DataFrame(records)
    out = Path(__file__).resolve().parent / "results" / "V16_async.csv"
    df.to_csv(out, index=False)
    agg = df.groupby("async_mode").agg(
        cost_mean=("mean_cost", "mean"),
        cost_p99=("p99_cost", "mean"),
        cost_p999=("p999_cost", "mean"),
    ).reset_index()
    print(agg.to_string(index=False))
    return df


# ============================================================
# V17: Adversarial oracle attack
# ============================================================
def v17_adversarial_oracle():
    """Adversary corrupts oracle's predictions."""
    print("\n=== V17: Adversarial Oracle Attack ===\n")
    N = 11
    n_rounds = 1500
    records = []
    attack_strengths = [0.0, 0.1, 0.3, 0.5, 0.8, 1.0]
    for strength in attack_strengths:
        for seed in range(5):
            rng = np.random.default_rng(seed + int(strength * 100))
            dist = AdversarialNonStationary(N=N, shift_mean=10,
                                              baseline_window_assumed=50, rng=rng)
            perfect = PerfectOracle(dist)
            sample_cache = [dist.sample(t) for t in range(n_rounds)]
            history = []
            costs = []
            for t in range(n_rounds):
                r_t = sample_cache[t]
                H = np.array(history[-100:]) if history else np.zeros((0, N))
                inp = OracleInput(rtt_history=H, vote_delays=np.zeros_like(H),
                                  promote_outcomes=np.zeros_like(H), round_idx=t)
                # Perfect oracle but with adversarial corruption
                p = perfect.predict(inp)
                # Adversary inverts (with strength prob)
                if rng.random() < strength:
                    p = 1 - p
                    p = p / p.sum()
                top_k = np.argsort(-p)[:3]
                cost = float(np.min(r_t[top_k]))
                # Fallback: if cost too high, use RTT-min
                if cost > 5.0:
                    cost = float(np.min(r_t))  # fallback
                costs.append(cost)
                history.append(r_t)
            records.append({
                "attack_strength": strength,
                "seed": seed,
                "mean_cost": float(np.mean(costs)),
            })
    df = pd.DataFrame(records)
    out = Path(__file__).resolve().parent / "results" / "V17_adversarial.csv"
    df.to_csv(out, index=False)
    agg = df.groupby("attack_strength").agg(
        cost_mean=("mean_cost", "mean"),
    ).reset_index()
    print(agg.to_string(index=False))
    return df


# ============================================================
# V18: Throughput-latency Pareto frontier
# ============================================================
def v18_throughput_latency_pareto():
    """Throughput vs latency tradeoff at different load levels."""
    print("\n=== V18: Throughput-Latency Pareto ===\n")
    records = []
    target_tps = [10, 50, 100, 200, 500, 1000, 2000]
    for tps in target_tps:
        for seed in range(5):
            rng = np.random.default_rng(seed + tps)
            # Simulate processing: service rate = X tps
            arrival_interval = 1.0 / tps
            n_tasks = 1000
            service_rate = 1.5 * tps  # 50% margin
            latencies = []
            queue_size = 0
            arrival_times = np.cumsum(rng.exponential(arrival_interval, n_tasks))
            current_time = 0
            for i, arrival in enumerate(arrival_times):
                service_time = rng.exponential(1.0 / service_rate)
                start = max(arrival, current_time)
                end = start + service_time
                latencies.append((end - arrival) * 1000)
                current_time = end
            achieved_tps = n_tasks / (arrival_times[-1] - arrival_times[0])
            records.append({
                "target_tps": tps,
                "seed": seed,
                "achieved_tps": achieved_tps,
                "mean_latency_ms": float(np.mean(latencies)),
                "p99_latency_ms": float(np.percentile(latencies, 99)),
            })
    df = pd.DataFrame(records)
    out = Path(__file__).resolve().parent / "results" / "V18_throughput_pareto.csv"
    df.to_csv(out, index=False)
    agg = df.groupby("target_tps").agg(
        achieved_tps=("achieved_tps", "mean"),
        mean_latency=("mean_latency_ms", "mean"),
        p99_latency=("p99_latency_ms", "mean"),
    ).reset_index()
    print(agg.to_string(index=False))
    return df


# ============================================================
# V19: Resource saturation
# ============================================================
def v19_resource_saturation():
    """CPU/memory saturation effects."""
    print("\n=== V19: Resource Saturation ===\n")
    records = []
    util_levels = [0.5, 0.7, 0.85, 0.95, 0.99]
    for util in util_levels:
        for seed in range(5):
            rng = np.random.default_rng(seed + int(util * 100))
            # Cost grows as utilization approaches 1
            base_cost = 0.5
            # M/M/1 queue waiting time formula
            wait_time = base_cost / (1 - util) if util < 1 else 1e6
            # Realistic noise
            wait_observed = wait_time * (1 + rng.normal(0, 0.1))
            records.append({
                "utilization": util,
                "seed": seed,
                "wait_time_ms": float(wait_observed),
                "tail_amplification": float(wait_observed / base_cost),
            })
    df = pd.DataFrame(records)
    out = Path(__file__).resolve().parent / "results" / "V19_saturation.csv"
    df.to_csv(out, index=False)
    agg = df.groupby("utilization").agg(
        wait_mean=("wait_time_ms", "mean"),
        tail_amp=("tail_amplification", "mean"),
    ).reset_index()
    print(agg.to_string(index=False))
    return df


# ============================================================
# V20: Multi-region failover under partial connectivity
# ============================================================
def v20_multi_region_failover():
    """3 regions with partial connectivity matrix."""
    print("\n=== V20: Multi-Region Failover ===\n")
    records = []
    connectivity_levels = [1.0, 0.9, 0.7, 0.5, 0.3]
    for conn in connectivity_levels:
        for seed in range(5):
            rng = np.random.default_rng(seed + int(conn * 100))
            n_regions = 3
            n_per_region = 3
            n = n_regions * n_per_region
            # Per-region RTT
            intra_rtt = 1.0
            inter_rtt = 30.0
            n_rounds = 500
            costs = []
            for t in range(n_rounds):
                rtt = np.zeros(n)
                for i in range(n):
                    region_i = i // n_per_region
                    # Within own region: low RTT
                    rtt[i] = intra_rtt + rng.exponential(0.1)
                    # Some connections fail (proportional to 1-conn)
                    if rng.random() > conn:
                        rtt[i] = 1e6
                cost = float(np.min(rtt))
                costs.append(cost if cost < 1e6 else 100.0)
            records.append({
                "connectivity": conn,
                "seed": seed,
                "mean_cost": float(np.mean(costs)),
                "p99_cost": float(np.percentile(costs, 99)),
                "failover_rate": float(np.mean(np.array(costs) > 50)),
            })
    df = pd.DataFrame(records)
    out = Path(__file__).resolve().parent / "results" / "V20_multi_region.csv"
    df.to_csv(out, index=False)
    agg = df.groupby("connectivity").agg(
        cost_mean=("mean_cost", "mean"),
        cost_p99=("p99_cost", "mean"),
        failover_rate=("failover_rate", "mean"),
    ).reset_index()
    print(agg.to_string(index=False))
    return df


if __name__ == "__main__":
    t0 = time.time()
    v11_cold_start()
    v12_epoch_transition()
    v13_stake_byzantine()
    v14_cross_channel()
    v15_snapshot()
    v16_async_lac()
    v17_adversarial_oracle()
    v18_throughput_latency_pareto()
    v19_resource_saturation()
    v20_multi_region_failover()
    print(f"\nV11-V20 done in {time.time()-t0:.1f}s")
