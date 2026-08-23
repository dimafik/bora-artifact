# Runbook — 5-Hour AWS Fabric Live Experiment

Self-contained execution kit for the pre-registered Schedulable Byzantine
Consensus live run. See `../AWS_5HR_EXPERIMENT_DESIGN.md` for the 7-expert
panel discussion that produced this design.

## Layout

```
runbook/
├── terraform/        Infrastructure-as-code (VPC, 5×c5n.4xlarge + 1×t3.large, S3)
├── ansible/          Configuration management (Fabric bootstrap, BRAO patch)
├── analysis/         aws_5h_analysis.py — pre-registered statistics pipeline
├── workloads/        Caliper workload module (transfer.js with criticality)
├── caliper/          Per-arm benchmark configs (arm-a / arm-b / arm-c / burst)
├── scripts/          Orchestration (preregister.sh, run_orchestrator.sh,
│                     dry_run_simulate.py)
├── dry_run_output/   Synthetic data + verified analysis pipeline output
└── preregister.hash  SHA-256 of all of the above (committed pre-T+0:00)
```

## Pre-run Checklist (T-24h)

1. Pre-bake the Fabric AMI (Docker + Go + Fabric 2.5.4 + Caliper + Node SDK).
2. Verify all tool versions match Appendix A of `AWS_5HR_EXPERIMENT_DESIGN.md`.
3. Run `python scripts/dry_run_simulate.py --out-dir dry_run_output` and
   confirm the synthetic analysis pipeline produces the expected report.
4. Run `bash scripts/preregister.sh > preregister.hash`.
5. Timestamp the hash via OpenTimestamps:
   `ots stamp preregister.hash` → commits to Bitcoin block.
6. Push hash + timestamp proof to a public location.

## Run Sequence (T+0:00)

```bash
bash scripts/run_orchestrator.sh 2026-06-01-r1
```

Orchestrator verifies hash, applies Terraform, runs Ansible, executes 5
arms with Caliper, syncs to S3, runs analysis, tears down. Logs to
`logs/<run_id>/orchestrator.log`.

## Abort Conditions

Automatic abort on:

- Any GO/NO-GO check failure (see Round 8 of design doc)
- $50 CloudWatch billing alarm (warning) / $60 (hard stop)
- Wall-clock > T+5:30 (hard kill)

On abort: orchestrator syncs `/data` to S3 under `aborted/`, runs
`terraform destroy`, exits non-zero.

## Post-run Artifacts

After T+5:00, the following are in `s3://schedulable-bft-<run_id>/runs/<run_id>/`:

- `arm_a/`, `arm_b/`, `arm_c/`, `burst/` — raw Caliper output per arm
- `raw/` — Prometheus snapshots, custom probe Parquet, container logs
- `analysis/` — `tables.tex`, `figs.pdf`, `REPORT.md`
- `preregister.hash` + OpenTimestamps proof

The S3 bucket should be made publicly readable within 7 days per the
reviewer-simulator (E7) commitment in the design document.

## Honesty Posture

This runbook is locked at preregister time. Any divergence — even fixing a
typo — invalidates the pre-registration and must be disclosed to reviewers
as an exploratory (not pre-registered) analysis.

The headline claim of the resulting paper section will be:

> Primary endpoint pre-registered before T+0:00; Holm-Bonferroni protected
> at α=0.001 over the family {primary normal-load, secondary burst-load};
> raw data available at s3://schedulable-bft-<run_id>/.
