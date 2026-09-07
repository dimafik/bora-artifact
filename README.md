# BORA — artefacts

Backing data, proofs and harness for

> **BORA: A Bounded Order-Risk Advisor for Provably Safe ML-Augmented Leader
> Election in Raft Consensus**
> Jin Woo Jung, Hoh Peter In (Korea University) — IEEE TNSE, Special Issue on
> Theoretical Intelligent Blockchain Networks

BORA attaches a bounded blacklist advisor to Raft leader election in Hyperledger
Fabric. The advisor may be wrong: its output maps to vanilla-Raft stuttering
steps under trace refinement, so a wrong prediction can withhold a timeout but
cannot break a safety invariant. This repository holds what the paper's numbers
rest on.

## Where the paper's claims live

| Claim in the paper | File |
|---|---|
| 720 forced elections; 21/240 unguarded, 0/240 operator-supplied, 0/240 detector-produced | `02_results_raw/x1_*/elections.csv` |
| Advice cap `\|B_t\| < f-r` held over 1,439 published advice observations | `02_results_raw/x1_*/elections.csv` (the `cap`/`size` columns) |
| The same cap audited against a rising `r`, 300 samples at N=11 | `02_results_raw/x1c_*/cap_audit.csv` |
| Four missed leader replacements in 480 guarded elections, none in 240 unguarded | `02_results_raw/x1_*/elections.csv` (the `live` column) |
| No target campaign inside a guarded election: 42 of 44 events, all unguarded | `02_results_raw/x1_*/logs/`, `01_testbed_harness/alg1/x1_campaign_audit.py` |
| Detection in 3.1 s, no false positive over 158 cycles | `02_results_raw/mldetect_20260611-171955/predictor_daemon.log` |
| All 21 unguarded wins had the target already in B_t at election start | `02_results_raw/x1_*/elections.csv` (`target_won`, `hits`, `list`) |
| Leader-vs-follower severity, 65% against 21% over 25 verified runs | `12_leader_severity/results/per_run_metrics.csv` |
| ALR ablation at N=7 over 360 forced elections | `02_results_raw/r13_merged.csv` |
| Physical five-host AWS: 147 guarded elections, 16 of them paired | `01_testbed_harness/alg1/xhost_bora_election.sh`, `02_results_raw/xhost_election_*`, `02_results_raw/mh_*` |
| Table IV — detector panel, incl. a 0-parameter statistic at AUC 1.00 | `08_predictor/r12_panel/panel2_results.json` |
| White-box PGD, worst-case AUC 0.003 over 1,152 runs (paper Fig. 7) | `08_predictor/r12_panel/panel2_results.json`, `10_figures/revision/mk_fig_whitebox.py` |
| Zero-parameter detector in the advisor slot: 0/240 forced elections, against 24/240 unguarded | `02_results_raw/b20_sweep_20260903-162221/`, `01_testbed_harness/alg1/b20_report.py` |
| Safety 48/48 (global and per-voter), exclusion 64/64, liveness 311/311 (no axioms) | `05_formal/tla/tlapm_out/` (tlapm transcripts), `05_formal/tla/run_tlapm.sh` (regenerates them) |
| Bounded safety model check: 66,849 states generated, 7,008 distinct, depth 12, no violation | `05_formal/tla/tlc_out/BORA.log` |
| Convergence rate | `05_formal/prism/` |
| What an evasive attack actually does (not in the paper) | `11_potency/` |

## Pre-registration

Conditions were fixed before results were seen. The paper follows the adaptive
evaluation protocol of Tramèr et al., under which that ordering is the point.

- `08_predictor/r12_panel/PREREGISTRATION.md`, `PREREG_R1R2.md`, `PREREG_D1D2.md`
- `12_leader_severity/prereg/PREREG_R25C.md`, `PREREG_R25D.md` and their addenda,
  with `.sha256` alongside — these are the ones Section V-D cites when it reports
  the clean-bracket threshold as a material confound

Runs that were discarded are kept rather than deleted, with the reason recorded
— see `11_potency/README.md`, which documents one campaign that ran to
completion and was void.

## What is not here

Bulk transcripts and rendered assets, listed with sizes in `MANIFEST.md`.
They regenerate from the scripts included here.

One set of numbers in the paper does not: the follower-delay throughput
percentages of Section V-D -- the 23% loss at 200-500 tx/s, the 9% at
100 tx/s, the +/-4% and 8% figures for the guarded arm, and the 1.1%
agreement across the twelve paired EC2 comparisons. Those come from a
rate-based clean-versus-attack comparison whose transcripts are not in this
package. What is here is each side separately and not the pairing: the clean
rate sweep in `02_results_raw/archive/5node_caliper_clean_2026-06-07`
(93.9 / 281.18 / 468.38 TPS at rate-100/300/500), and a delay-injection
study in `02_results_raw/archive/5node_attack_2026-06-07` that sweeps
concurrency rather than rate. A reader can check the clean side and the
shape of the attack, and cannot recompute the percentages themselves.

The election result those percentages sit beside *is* here and is the claim
the section rests on: 74 forced elections across the load sweep with the
target at zero (`02_results_raw/loadsweep_*`), and the leader-versus-follower
severity study in `12_leader_severity/`.

Private keys and credentials are excluded by pattern and the package was
re-scanned after assembly; the scan found none.

## Environment

Every single-host measurement in the paper was produced on **one machine**: a
20-thread Intel i7-12700K under Docker Desktop, with 16 GB allocated to the
engine, Windows 11 + WSL2. **No container is CPU-pinned and no CPU limit is
set**, and the predictor daemon sets no process affinity, disables no GC and
locks no memory.

An earlier version of the paper described the fixed-N results as running on a
14-core Xeon E5-2680 v4 with orderer containers pinned to disjoint cores, and
the closed-loop sweep as a second testbed. That was wrong; it is corrected in
the revision. How it was checked, so the claim above can be rechecked:

* `compose/5node-raft.yaml` sets no `cpus`, `cpuset`, `deploy` or `resources`,
  and no script in this package calls `taskset` or `numactl`.
* `docker inspect` on the live orderers reports `CpusetCpus=[]` and
  `NanoCpus=0`, which is where a runtime `docker update --cpuset-cpus` would
  otherwise show up.
* `docker info` reports `CPUs=20`, `MemTotal=16646320128` and Docker Desktop
  `27.3.1`, matching the `host_os` and `host_memory_gb_allocated_to_docker`
  fields recorded in `02_results_raw/archive/*/metadata.json` from June 2026.

The genuine split is in software, not hardware. The exclusion, throughput and
closed-loop results run against **Fabric v3.1.4** (`alg1/build_v3.sh`,
`build_v4.sh`). The one exception is the ~530 tx/s commit ceiling, which comes
from `02_results_raw/archive/5node_saturation_delta_2026-06-08`
(`TPS_mean 527.77`) on **Fabric v2.5.10**; it is retained because it is the only
saturation measurement taken, and the paper says so where it is used.

## Reproducing

Each directory carries its own notes. Start from `11_potency/README.md` for the
election and throughput harness, and `05_formal/` for the proofs.

## Citing

Please cite the paper. If you use the artefacts directly, the archived snapshot
carries its own DOI.
