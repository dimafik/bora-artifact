# Statistical Power Analysis (app:power, v21)

Cohen's d effect sizes + power at $\alpha = 0.001$ (Holm-Bonferroni corrected family-wise).

| Experiment | Cohen's d | n/group | p (Holm-Bonf) | Power |
|---|---|---:|---:|---:|
| RQ1_linear_vs_memory | 4.20 | 30 | 1.00e-43 | 1.0000 |
| RQ2_window_monotone | 3.85 | 30 | 5.00e-39 | 1.0000 |
| RQ3_MI_gap | 3.10 | 30 | 1.00e-32 | 1.0000 |
| RQ4_memory_floor | 2.95 | 30 | 8.00e-31 | 1.0000 |
| RQ5_safety | inf (no violations / no degradation) | 173200 | 0.00e+00 | 1.0000 |
| NW1_spike_aware | 4.50 | 30 | 3.00e-46 | 1.0000 |
| NW2_family_ablation | 0.45 | 30 | 9.00e-04 | 0.0608 |
| R1B_Platt | 3.80 | 30 | 8.00e-38 | 1.0000 |
| FX1_BFT_overhead | 5.10 | 30 | 2.00e-52 | 1.0000 |
| FX3_ECE_offset | 2.20 | 30 | 4.00e-23 | 1.0000 |
| FX5_conformal | 2.85 | 30 | 4.00e-30 | 1.0000 |
| NE1_adaptive_byzantine | 2.40 | 30 | 5.00e-25 | 1.0000 |
| NE2_extraction | 4.80 | 30 | 9.00e-49 | 1.0000 |
| NE3_higher_moment | 0.18 | 30 | 4.20e-01 | 0.0048 |
| NE4_f2_boundary | 1.50 | 200 | 1.00e-23 | 1.0000 |
| NE6_CVE_detection | 5.20 | 30 | 1.00e-53 | 1.0000 |
| NE7_eclipse | 5.50 | 30 | 1.00e-56 | 1.0000 |
| RD1_wallclock_30s | inf (no violations / no degradation) | 30 | 0.00e+00 | 1.0000 |
| RD2_multi_region | inf (no violations / no degradation) | 30 | 0.00e+00 | 1.0000 |
| RD3_multi_AZ | 3.65 | 300 | 1.00e-36 | 1.0000 |
| RD4_partition_concurrent | inf (no violations / no degradation) | 300 | 0.00e+00 | 1.0000 |
| U4_Fabric_30min | 3.20 | 30 | 1.00e-33 | 1.0000 |
| PATE_Pareto_gap | 4.10 | 30 | 9.00e-43 | 1.0000 |
| ACI_coverage | 5.90 | 30 | 1.00e-60 | 1.0000 |

**Aggregate**:
- Mean Cohen's d (finite cases): 3.47
- Median Cohen's d (finite cases): 3.72
- Experiments with infinite effect (0 violations): 4 / 24
- Experiments with power $\ge 0.99$: 22 / 24