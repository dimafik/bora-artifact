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
| No campaign by a blacklisted node inside a guarded election window (the guarded count is zero under every delimitation; totals range 35–69 by definition) | `01_testbed_harness/alg1/x1_campaign_audit.py`; the per-arm raft logs (736 MB) are kept on the testbed host, not shipped |
| Detection in 3.1 s, no false positive over 158 cycles | `02_results_raw/mldetect_20260611-171955/predictor_daemon.log` |
| All 21 unguarded wins had the target already in B_t at election start | `02_results_raw/x1_*/elections.csv` (`target_won`, `hits`, `list`) |
| Leader-vs-follower severity: a degraded leader stalled 13 of 36 runs (95–100% of submissions failed), median 14% failures, latency 17×; a degraded follower failed nothing in 33 of 36 | `12_leader_severity/results/per_run_metrics.csv`, the per-run `summary.txt` success/failure columns |
| ALR ablation at N=7 over 360 scheduled forced elections (159 demotions) | `02_results_raw/r13v3_alr_ablation/` (`r13_merged.csv` is the discarded v2 design) |
| Physical five-host AWS: 147 guarded elections, 16 of them paired | `01_testbed_harness/alg1/xhost_bora_election.sh`, `02_results_raw/xhost_election_*`, `02_results_raw/mh_*` |
| Table IV — detector panel, incl. a 0-parameter statistic at AUC 1.00 | `08_predictor/r12_panel/panel2_results.json` |
| White-box PGD, worst-case AUC 0.003 over 1,152 runs (paper Fig. 6) | `08_predictor/r12_panel/panel2_results.json`, `10_figures/revision/mk_fig_whitebox.py` |
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

An earlier version of this section said the follower-delay figures of
Section V-D and the EC2 1.1% agreement could not be recomputed from this
package. They can: `02_results_raw/auto6h_run/MASTER_SUMMARY.txt` (EXP-B, three
seeds, clean/attack/guarded) holds the 23%, 9%, +/-4% and 8%, and
`02_results_raw/mh_final_N{5,7,9,11}.txt` the twelve EC2 pairs. Every
transaction committed in every EXP-B arm; the 23% and 9% are Caliper's rate
figure, which falls because the slowest commits stretch its time span, and
Section V-D now reports them that way.

The election results beside them are here too: 74 forced elections on an idle
cluster with the target at zero (`02_results_raw/loadsweep_*`; Caliper
committed nothing because the chaincode was not deployed on that network, so
there was no ordering load), and the leader-versus-follower severity study in
`12_leader_severity/`.

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

Those metadata files carry more than environment fields, and the rest of what
they carry describes a different manuscript. Their `title`,
`current_version`, `section_using_archives` and `paper_table` fields name the
June 2026 paper that preceded BORA -- a different title, sections VII and VIII,
and tables `tab:d2-conc`, `tab:d2-caliper`, `tab:d2-attack`, `tab:d2-alg1` and
`tab:d2-saturation`. This paper has no such tables and its sections run I to
VII. The fields are kept as written because they record what each run was for
at the time it was made, which is what makes the archive usable as provenance
at all.

What this paper takes from that archive is narrow: the environment fields
above, the ~530 tx/s ceiling from `5node_saturation_delta_2026-06-08`, and the
clean rate sweep in `5node_caliper_clean_2026-06-07` that Section V-D's
throughput paragraph sits beside. Nothing else in it is cited, and no table in
this paper is named by a `paper_table` field.

The genuine split is in software, not hardware. The exclusion, throughput and
closed-loop results run against **Fabric v3.1.4** (`alg1/build_v3.sh`,
`build_v4.sh`). The one exception is the ~530 tx/s commit ceiling, which comes
from `02_results_raw/archive/5node_saturation_delta_2026-06-08`
(`TPS_mean 527.77`) on **Fabric v2.5.10**; it is retained as that host's
ceiling. The patched v3.1.4 build later reached 555–595 tx/s on the same host by
the same measure (`02_results_raw/auto6h_run/`, EXP-B clean, rate-600/700).

## Reproducing

Each directory carries its own notes. Start from `11_potency/README.md` for the
election and throughput harness, and `05_formal/` for the proofs.

## Citing

Please cite the paper. If you use the artefacts directly, the archived snapshot
carries its own DOI.
