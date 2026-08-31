# BORA artefact package

Backing data for *BORA: A Bounded Order-Risk Advisor for Provably Safe
ML-Augmented Leader Election in Raft Consensus* (IEEE TNSE).

## Included in full

- `05_formal`
- `08_predictor`
- `11_potency`
- `01_testbed_harness`
- `12_leader_severity`

## Included by file type

- `02_results_raw` — .csv, .json, .md, .txt
- `03_caliper` — .json, .yaml, .yml, .md
- `09_runbook_aws` — .tf, .yml, .yaml, .sh, .md, .hash, .ots, .json
- `10_figures` — .py, .md, .sh

## Deliberately omitted

Bulk transcripts and rendered assets that no number in the paper depends on. They are reproducible from the scripts included here.


## Removed after the first release

`07_theory_scripts` (180 files) and six files at the top of `05_formal`
(`ISRaftMC*.tla`, `TLA_PLUS_VERIFICATION_LOG.md`, `Apalache_README.md`, and the
old `05_formal/README.md`) were shipped in error. They belong to a different
paper on mixed-criticality scheduling: mode switching, CPL/PSR, schedulability,
KZG witness commitments. Checked before removal — files in `07_theory_scripts`
mentioning BORA: **0**; times the BORA manuscript references that directory:
**0**. Removed 2026-08-26.

A caveat on that test. This project's own working directory was named
`IS-Raft-LAC` before the system was renamed to BORA, and that fragment still
appears in 36 files here: 15 TLC logs, 12 shell scripts, 8 Python scripts and
one text file. Those paths refer to *this* work, not to the removed paper, so
"files mentioning BORA: 0" shows only that the rename post-dates them. The logs
are kept verbatim because they are records of runs that actually happened;
editing them would misrepresent what was executed.

## Not included, by policy

Private keys and credentials are excluded by pattern (`*.pem`, `*.key`, `*.ppk`, `id_rsa*`, `*.pfx`, `*.p12`) and the package is re-scanned after assembly. The scan found none.
