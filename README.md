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
| Leader-vs-follower severity, 65% against 21% over 25 verified runs | `12_leader_severity/results/per_run_metrics.csv` |
| ALR ablation at N=7 over 360 forced elections | `02_results_raw/r13_merged.csv` |
| Physical five-host AWS: 147 guarded elections, 16 of them paired | `09_runbook_aws/`, `02_results_raw/mh_*` |
| Table II — detector panel, incl. a 0-parameter statistic at AUC 1.00 | `08_predictor/r12_panel/panel2_results.json` |
| White-box PGD, worst-case AUC 0.003 over 1,152 runs (paper Fig. 7) | `08_predictor/r12_panel/panel2_results.json`, `10_figures/revision/mk_fig_whitebox.py` |
| Safety 48/48 (global and per-voter), exclusion 64/64, liveness 311/311 (no axioms) | `05_formal/tla/tlapm_out/` (tlapm transcripts), `05_formal/tla/run_tlapm.sh` (regenerates them) |
| Convergence rate | `05_formal/prism/` |
| What an evasive attack actually does (not in the paper) | `11_potency/` |

## Pre-registration

Conditions were fixed before results were seen. The paper follows the adaptive
evaluation protocol of Tramèr et al., under which that ordering is the point.

- `08_predictor/r12_panel/PREREGISTRATION.md`, `PREREG_R1R2.md`, `PREREG_D1D2.md`
- `09_runbook_aws/preregister.hash` with an OpenTimestamps proof (`.ots`)

Runs that were discarded are kept rather than deleted, with the reason recorded
— see `11_potency/README.md`, which documents one campaign that ran to
completion and was void.

## What is not here

Bulk transcripts and rendered assets that no number depends on, listed with
sizes in `MANIFEST.md`. They regenerate from the scripts included here.

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
