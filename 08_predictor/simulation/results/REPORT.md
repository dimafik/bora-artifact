# 4-Arm Simulation Results

**N events per arm**: 100
**N Byzantine eval**: 400
**N degradation eval**: 200
**Pre-registered alpha**: 0.001
**Family-wise control**: Holm-Bonferroni

## Per-Arm Recovery Time Summary

| Arm | Median (ms) | P99 (ms) | Mean ± SD |
|---|---:|---:|---:|
| A | 263.4 | 339.2 | 263.7 ± 45.1 |
| B | 202.1 | 336.2 | 160.4 ± 120.0 |
| C | 216.4 | 331.6 | 163.1 ± 122.3 |
| D | 199.7 | 328.5 | 157.5 ± 118.1 |

## H1: Recovery Time (Arm A vs Arm D, one-sided Wilcoxon)
- Median difference (A − D): **106.1 ms**
- Hodges-Lehmann 99% CI: [213.0, 300.1] ms
- p-value: **2.66e-10**
- Reject H0 at α=0.001: **YES**

## H2: Byzantine Anomaly AUC (Arm D vs Arm A)
- Arm A AUC (score-formula baseline, ceiling theorem): 0.5000
- Arm D AUC (ML predictor): **0.6248**
- Difference: 0.1248
- 99% bootstrap CI for diff: [0.0495, 0.1942]
- 99% CI lower bound > 0.15: **NO**

## H3: Maintenance Precision@10% (1-hour Degrade Horizon)
- Top-10% selected: 20 of 200
- True positives in top-10%: 20
- Precision@10%: **1.0000**
- Wilson 99% CI: [0.7509, 1.0000]
- Lower bound ≥ 0.70: **YES**
- Degrade AUC: 0.8435

## Holm-Bonferroni Family Control (α=0.001)

| Test | Raw p | Threshold | Reject? |
|---|---:|---:|:---:|
| H1 | 2.66e-10 | 3.33e-04 | YES |
| H3 | 1.00e-03 | 5.00e-04 | NO |
| H2 | 5.00e-01 | 1.00e-03 | NO |
