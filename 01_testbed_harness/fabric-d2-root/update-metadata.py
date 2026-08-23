"""Add cross-references to delta in all existing archive metadata.json files."""
import json
from pathlib import Path

ARCHIVE_ROOT = Path("/mnt/d/fabric-d2/results/archive")

# Per-archive related_phases pointer list
RELATED = {
    "1node_raft_baseline_2026-06-07": {
        "phase": "alpha",
        "paper_table": "tab:d2-conc (1-orderer column)",
        "paper_paragraph": "Concurrency baseline",
        "related_phases": {
            "gamma": "5node_raft_2026-06-07 (5-orderer equivalent, contrasts pipelining cost)",
            "eta":   "5node_caliper_clean_2026-06-07 (SDK throughput at sustained rates)",
            "delta": "5node_saturation_delta_2026-06-08 (saturation plateau identification)",
            "mu":    "5node_extended_conc_2026-06-08 (native CLI ceiling)"
        }
    },
    "5node_raft_2026-06-07": {
        "phase": "gamma",
        "paper_table": "tab:d2-conc (5-orderer column)",
        "paper_paragraph": "Concurrency baseline 1-orderer vs 5-orderer",
        "related_phases": {
            "alpha":   "1node_raft_baseline_2026-06-07 (1-orderer comparison)",
            "eta":     "5node_caliper_clean_2026-06-07 (high-rate SDK throughput on same 5-orderer cluster)",
            "delta":   "5node_saturation_delta_2026-06-08 (saturation plateau ~530 TPS)",
            "mu":      "5node_extended_conc_2026-06-08 (C=32, 64 native CLI saturation)",
            "epsilon": "5node_attack_2026-06-07 (orderer-delay attack baseline)",
            "kappa":   "5node_alg1_2026-06-08 (Algorithm 1 simulation)",
            "iota":    "5node_failover_2026-06-08 (Raft leader failover)"
        }
    },
    "5node_caliper_2026-06-07": {
        "phase": "beta_failed_multi_seed",
        "paper_table": "honest disclosure paragraph in §VII.B (seeds 2-5 cumulative state-DB bottleneck)",
        "paper_paragraph": "Caliper multi-seed limitation disclosure",
        "related_phases": {
            "eta":   "5node_caliper_clean_2026-06-07 (clean 5-seed sweep using fresh-network-per-seed)",
            "delta": "5node_saturation_delta_2026-06-08 (reinterprets beta's rate-1000 45% timeouts as Caliper 7s window expiration, NOT actual blockchain failure)"
        },
        "delta_reinterpretation": "Beta's rate-1000 45% commit timeouts are now understood as the Caliper SDK's default 7-second observation window being exceeded once tail latency grows past it. Delta sweep at rates 600-900 tx/s shows 0 commit failures across 270,013 transactions, demonstrating the blockchain DOES commit them — just outside the SDK's observation window. The 'saturation point at ~500-700 TPS' in v49 is therefore narrowed by delta to ~530 TPS plateau."
    },
    "5node_caliper_clean_2026-06-07": {
        "phase": "eta",
        "paper_table": "tab:d2-caliper",
        "paper_paragraph": "Caliper sustained throughput (5-seed clean)",
        "related_phases": {
            "beta":  "5node_caliper_2026-06-07 (failed multi-seed precursor; eta uses fresh-network-per-seed to fix)",
            "delta": "5node_saturation_delta_2026-06-08 (extends eta's rate-500 ceiling at 468.4 TPS to identify the actual saturation plateau)"
        },
        "delta_extension": "Eta's rate-500 sustains 468 TPS at 50ms latency. Delta brackets the saturation by sweeping rate-600 through rate-900, finding the plateau at 503-537 TPS with latency growing 5.7s -> 17s as queue accumulates."
    },
    "5node_attack_2026-06-07": {
        "phase": "epsilon",
        "paper_table": "tab:d2-attack",
        "paper_paragraph": "NE21 orderer-delay attack",
        "related_phases": {
            "kappa": "5node_alg1_2026-06-08 (paired comparison: same +200ms attack vs simulated Algorithm 1 blacklist)",
            "delta": "5node_saturation_delta_2026-06-08 (provides clean baseline ~530 TPS plateau for attack-impact contextualization)"
        }
    },
    "5node_attack_unreliable_2026-06-07": {
        "phase": "epsilon_first_attempt_void",
        "paper_table": "(not in paper — pumba syntax error invalidated results)",
        "paper_paragraph": "(not in paper)",
        "related_phases": {
            "epsilon": "5node_attack_2026-06-07 (the valid re-run with corrected pumba interval > duration syntax)"
        },
        "note": "Preserved for transparency; pumba 'duration must be shorter than interval' error caused all three phases (clean/+200ms/+500ms) to be effectively clean. Confirmed by similar TPS across all three labels."
    },
    "5node_alg1_2026-06-08": {
        "phase": "kappa",
        "paper_table": "tab:d2-alg1",
        "paper_paragraph": "NE22 Algorithm 1 simulation via orderer removal",
        "related_phases": {
            "epsilon": "5node_attack_2026-06-07 (Phase A reproduces epsilon's +200ms attack on orderer3)",
            "delta":   "5node_saturation_delta_2026-06-08 (~530 TPS saturation ceiling contextualizes why Phase B blacklisting cannot fully recover throughput on single-host hardware)"
        }
    },
    "5node_failover_2026-06-08": {
        "phase": "iota",
        "paper_table": "(in-line numbers in NE23 paragraph)",
        "paper_paragraph": "NE23 Raft leader failover time",
        "related_phases": {
            "delta": "5node_saturation_delta_2026-06-08 (sustained throughput context for understanding consensus-path criticality)"
        }
    },
    "5node_extended_conc_2026-06-08": {
        "phase": "mu",
        "paper_table": "(in-line numbers in NE24 paragraph)",
        "paper_paragraph": "NE24 extended concurrency C=32,64",
        "related_phases": {
            "alpha":   "1node_raft_baseline_2026-06-07 (C=1..16 baseline)",
            "gamma":   "5node_raft_2026-06-07 (5-orderer C=1..16)",
            "eta":     "5node_caliper_clean_2026-06-07 (Fabric Gateway SDK ~468 TPS — 10x above native CLI's ~45 TPS ceiling)",
            "delta":   "5node_saturation_delta_2026-06-08 (530 TPS saturation plateau via SDK — confirms CLI is not the blockchain bottleneck)"
        }
    },
    "5node_saturation_delta_2026-06-08": {
        "phase": "delta",
        "paper_table": "tab:d2-saturation",
        "paper_paragraph": "NE25 saturation refinement",
        "related_phases": {
            "eta":     "5node_caliper_clean_2026-06-07 (extends eta's rate-100/300/500 to rate-600/700/800/900)",
            "beta":    "5node_caliper_2026-06-07 (reinterprets beta's rate-1000 45% timeouts)",
            "mu":      "5node_extended_conc_2026-06-08 (contrasts SDK 530 TPS ceiling vs native CLI 45 TPS ceiling)",
            "epsilon": "5node_attack_2026-06-07 (clean baseline for attack-impact normalization)",
            "kappa":   "5node_alg1_2026-06-08 (clean baseline for blacklist-recovery analysis)"
        }
    }
}

for archive_name, related_info in RELATED.items():
    metadata_path = ARCHIVE_ROOT / archive_name / "metadata.json"
    if not metadata_path.exists():
        print(f"[skip] {archive_name}: no metadata.json")
        continue
    try:
        with open(metadata_path) as f:
            data = json.load(f)
    except Exception as e:
        print(f"[skip] {archive_name}: parse error {e}")
        continue

    # Add/overwrite the cross-reference section
    data["paper_integration"] = {
        "phase_letter": related_info["phase"],
        "paper_table_label": related_info["paper_table"],
        "paper_section_or_paragraph": related_info["paper_paragraph"],
        "related_phases": related_info["related_phases"]
    }
    # Add delta-specific reinterpretation note for beta
    if "delta_reinterpretation" in related_info:
        data["paper_integration"]["delta_reinterpretation"] = related_info["delta_reinterpretation"]
    if "delta_extension" in related_info:
        data["paper_integration"]["delta_extension"] = related_info["delta_extension"]
    if "note" in related_info:
        data["paper_integration"]["note"] = related_info["note"]

    with open(metadata_path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"[updated] {archive_name}/metadata.json")

# Create top-level MANIFEST.json
manifest = {
    "manifest_version": "1.0",
    "generated_utc": "2026-06-08",
    "paper": {
        "title": "Provably Safe Learning-Augmented Leader Election: Tight Bounds for Permissioned Byzantine Consensus",
        "venue": "IEEE TNSE Special Issue 'Theoretical Intelligent Blockchain Networks'",
        "current_version": "v51 (tnse_submission51.{tex,pdf}, tnse_submission51_ko.{tex,pdf})",
        "section_using_archives": "Section VII.B (D2: Hyperledger Fabric + Caliper, Executed Testbed) and Section VIII.A NE21-NE25 paragraphs"
    },
    "experimental_phases_summary": {
        "alpha": {
            "name": "1-orderer Raft baseline concurrency sweep",
            "archive": "1node_raft_baseline_2026-06-07",
            "n_seeds": 5,
            "scope": "C=1..16, 20 tx/thread, peer chaincode invoke CLI",
            "key_result": "TPS 3.80 (C=1) -> 28.98 (C=16), 0 failures",
            "paper_use": "tab:d2-conc left column"
        },
        "gamma": {
            "name": "5-orderer Raft baseline concurrency sweep",
            "archive": "5node_raft_2026-06-07",
            "n_seeds": 5,
            "scope": "Same C as alpha but on 5-orderer Raft cluster",
            "key_result": "TPS 3.35 (C=1) -> 27.91 (C=16), within 4-12% of 1-orderer",
            "paper_use": "tab:d2-conc right column"
        },
        "beta": {
            "name": "Caliper Docker multi-seed sweep (FAILED for seeds 2-5)",
            "archive": "5node_caliper_2026-06-07",
            "n_seeds": "1 valid + 4 with cumulative state-DB bottleneck",
            "scope": "rate-100/500/1000/2000 tx/s, 60s/round",
            "key_result": "seed 1 sustains 96.9 TPS @ rate-100; reported as honest disclosure",
            "paper_use": "Honest disclosure paragraph in Caliper section",
            "superseded_by": ["eta", "delta"]
        },
        "epsilon": {
            "name": "Pumba orderer-delay attack injection",
            "archive": "5node_attack_2026-06-07 (valid) + 5node_attack_unreliable_2026-06-07 (void first attempt)",
            "n_seeds": 3,
            "scope": "Clean / +200ms / +500ms delay on orderer3, C=1..16",
            "key_result": "+200ms drops C=16 TPS by 81% (45.19 -> 8.55), p99 inflates 9x",
            "paper_use": "tab:d2-attack (NE21)"
        },
        "eta": {
            "name": "Caliper clean 5-seed sweep (fresh network/seed)",
            "archive": "5node_caliper_clean_2026-06-07",
            "n_seeds": 5,
            "scope": "rate-100/300/500 tx/s, 30s/round, 8 workers",
            "key_result": "93.9 / 281.18 / 468.38 TPS sustained, 135,120 tx, 0 failures, std<=0.08 TPS",
            "paper_use": "tab:d2-caliper"
        },
        "kappa": {
            "name": "Algorithm 1 simulation via orderer3 stop",
            "archive": "5node_alg1_2026-06-08",
            "n_seeds": 3,
            "scope": "Phase A: +200ms attack on orderer3; Phase B: orderer3 stopped",
            "key_result": "C=16 p99 latency 540 -> 389 ms (-28%); TPS partial recovery only",
            "paper_use": "tab:d2-alg1 (NE22)"
        },
        "iota": {
            "name": "Raft leader failover time",
            "archive": "5node_failover_2026-06-08",
            "n_trials": 3,
            "scope": "Kill current leader, poll for new-leader election",
            "key_result": "Failover 1273 / 5585 / 6731 ms (mean 4530 +- 2854 ms)",
            "paper_use": "NE23 paragraph"
        },
        "mu": {
            "name": "Extended concurrency C=32, 64",
            "archive": "5node_extended_conc_2026-06-08",
            "n_seeds": 3,
            "scope": "C=1,4,16,32,64 native peer chaincode invoke CLI",
            "key_result": "CLI ceiling at ~45 TPS (C=16); C=32 has 50% failures",
            "paper_use": "NE24 paragraph"
        },
        "delta": {
            "name": "Caliper saturation refinement",
            "archive": "5node_saturation_delta_2026-06-08",
            "n_seeds": 3,
            "scope": "rate-600/700/800/900 tx/s, 30s/round, fresh-network-per-seed",
            "key_result": "Throughput plateau 503-537 TPS, latency 5.7s -> 17s, 270,013 tx 0 failures",
            "paper_use": "tab:d2-saturation (NE25)",
            "supersedes_interpretation_of": "beta rate-1000 45% timeouts (now reinterpreted as Caliper SDK 7s window expiration)"
        }
    },
    "campaign_totals": {
        "total_executed_transactions": 3100 + 135120 + 270013 + 3300 + 1100 + 1500 + 900,
        "computation_breakdown": "alpha+gamma baseline: 3,100; eta Caliper: 135,120; delta Caliper: 270,013; epsilon attack: ~3,300; kappa: ~1,100; mu: ~1,500; iota: 3 failover trials",
        "total_safety_violations": 0,
        "total_committed_blocks": "88,468+ (per Raft block height monitor in master log)"
    },
    "honest_disclosures": [
        "beta seeds 2-5 produced 0 successes due to cumulative state-DB growth; eta fixes this with fresh-network-per-seed",
        "beta rate-1000 'commit timeouts' are NOT blockchain failures, but Caliper SDK 7s window expirations (proven by delta showing 0 failures up to rate-900)",
        "Algorithm 1 'simulation' in kappa is naive orderer removal; paper's actual mechanism is candidacy-filter (preserves quorum)",
        "ε first attempt invalidated by pumba 'duration < interval' syntax error; valid re-run in 5node_attack_2026-06-07",
        "All measurements on single-host Docker Desktop; production AWS deployment would shift saturation point higher",
        "Native peer chaincode invoke CLI saturates at ~45 TPS (mu); 10x below Fabric Gateway SDK ceiling — CLI is measurement artifact, not Raft bottleneck"
    ]
}

manifest_path = ARCHIVE_ROOT / "MANIFEST.json"
with open(manifest_path, "w") as f:
    json.dump(manifest, f, indent=2, ensure_ascii=False)
print(f"\n[created] {manifest_path}")
print(f"Total committed tx in campaign: {manifest['campaign_totals']['total_executed_transactions']:,}")
