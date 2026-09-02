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
| Advice cap `\|B_t\| < f-r` held over 1,439 published cycles | `02_results_raw/x1c_*/cap_audit.csv` |
| Table II — detector panel, incl. a 0-parameter statistic at AUC 1.00 | `08_predictor/r12_panel/panel2_results.json` |
| White-box PGD, worst-case AUC 0.003 over 1,152 runs | `08_predictor/r12_panel/panel2_results.json` |
| Safety 48/48, per-voter 48/48, liveness 311/311 (no axioms) | `05_formal/tla/` |
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
