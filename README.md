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

## Reproducing

Each directory carries its own notes. Start from `11_potency/README.md` for the
election and throughput harness, and `05_formal/` for the proofs.

## Citing

Please cite the paper. If you use the artefacts directly, the archived snapshot
carries its own DOI.
