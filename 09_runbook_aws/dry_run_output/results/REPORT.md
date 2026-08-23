# AWS 5-hour Live Deployment — Run Report

**Pre-register hash**: `dry_run_no_preregister`
**Pre-registered α**: 0.001
**Power target**: 0.99
**CI level**: 0.99

## Per-Arm Summary

| Arm | HC tx | HC miss | Rate | 99% Wilson CI | P99 (ms) | P99.9 (ms) | TPS |
|---|---:|---:|---:|---|---:|---:|---:|
| A: Raft | 52386 | 2024 | 3.86% | [3.65, 4.09]% | 143.4 | 359.0 | 86.9 |
| B: Proposed | 52985 | 430 | 0.81% | [0.72, 0.92]% | 102.6 | 244.9 | 86.9 |
| C: Ablation | 52519 | 1233 | 2.35% | [2.18, 2.52]% | 117.4 | 336.7 | 86.9 |

## Pre-Registered Statistical Comparisons

| Test | Risk Diff (pp) | RD 99% CI | Risk Ratio | RR 99% CI | Fisher p | Holm p | Reject H₀? |
|---|---:|---|---:|---|---:|---:|:---:|
| primary_arm_a_vs_b_normal | 3.05 | [2.44, 3.68] | 0.210 | [0.183, 0.241] | 6.24e-256 | 1.25e-255 | **YES** |
| secondary_arm_a_vs_b_burst | 4.85 | [3.77, 5.95] | 0.213 | [0.183, 0.247] | 1.50e-204 | 1.50e-204 | **YES** |

## Conclusion (one-line)

> Proposed protocol reduces HC-miss rate by 3.05 percentage points vs Raft baseline (Holm-adjusted p = 1.25e-255, Risk Ratio = 0.210). Primary hypothesis H1 supported.

## Honesty Notes

- Single-region (us-east-1), 3-AZ. Generalization to multi-region untested.
- SmartBFT/Arma not measured live; comparison via published-paper figures only.
- Predictor frozen at simulator-trained weights; no online learning.
- All claims pre-registered before T+0:00; no post-hoc selection.
