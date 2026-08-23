# v28 Round-Based Refinement Experiments (8 Refined)

**Seeds**: 30

## R1A — Graduated Byzantine Intensity
| Intensity | AUC | FP | TP |
|---:|---:|---:|---:|
| 0.01 | 0.998 | 0.301 | 1.000 |
| 0.05 | 0.998 | 0.301 | 1.000 |
| 0.10 | 0.998 | 0.301 | 1.000 |
| 0.20 | 0.998 | 0.301 | 1.000 |
| 0.30 | 0.998 | 0.301 | 1.000 |
| 0.50 | 0.998 | 0.301 | 1.000 |
| 0.75 | 0.998 | 0.301 | 1.000 |
| 1.00 | 0.998 | 0.301 | 1.000 |

## R1B — Platt Calibration ECE/Brier
- ECE pre: 0.255 ± 0.009 → post: 0.014 ± 0.004
- Brier pre: 0.115 ± 0.006 → post: 0.014 ± 0.005

## R1C — Training-Set-Scale
| n | AUC mean ± std |
|---:|---:|
| 50 | 0.999 ± 0.001 |
| 100 | 0.998 ± 0.002 |
| 200 | 0.998 ± 0.001 |
| 400 | 0.998 ± 0.001 |
| 800 | 0.998 ± 0.001 |
| 1600 | 0.998 ± 0.000 |
| 3200 | 0.998 ± 0.000 |

## R2A — Network Partition Recovery (median ms)
| Partition dur | Recovery (van) | Recovery (AI) |
|---:|---:|---:|
| 100 ms | 260.9 | 34.0 |
| 500 ms | 260.9 | 34.0 |
| 1000 ms | 260.9 | 34.0 |
| 2000 ms | 260.9 | 34.0 |
| 5000 ms | 260.9 | 34.0 |

## R2B — Adversarial Timing Coincidence
| Coincidence | Mean AUC | Min AUC |
|---:|---:|---:|
| 0.00 | 0.970 | 0.950 |
| 0.25 | 0.874 | 0.551 |
| 0.50 | 0.773 | 0.550 |
| 0.75 | 0.672 | 0.550 |
| 1.00 | 0.575 | 0.550 |

## R3A — Realistic Fabric Orderer (3-Phase BFT)
| TPS | p50-van | p50-ai | p50-bft | p99-van | p99-ai | p99-bft |
|---:|---:|---:|---:|---:|---:|---:|
| 100 | 6.44 | 6.24 | 20.36 | 13.92 | 12.71 | 31.23 |
| 500 | 6.44 | 6.24 | 20.36 | 13.92 | 12.71 | 31.23 |
| 1000 | 6.44 | 6.24 | 20.36 | 13.92 | 12.71 | 31.23 |
| 1500 | 6.44 | 6.24 | 20.36 | 13.92 | 12.71 | 31.23 |
| 2000 | 8.58 | 8.32 | 27.15 | 18.56 | 16.94 | 41.64 |

## R3B — Stress-To-Break Safety
- Total events: 60,000
- Total violations: **0**
- Fail-open count: 36,293
- Per mode: {'max_risk': 0, 'max_conf_noise': 0, 'coord_attack': 0}

## R4A — Long-Horizon Stability (10K ticks)
- Mean flags per seed: 3012.43 ± 41.06
- MTBFD: 3 ticks

## R4B — 24-Channel Family Ablation
| Ablated family | AUC mean ± std |
|---|---:|
| A_latency | 1.000 ± 0.000 |
| B_reliab | 1.000 ± 0.000 |
| C_elect | 1.000 ± 0.000 |
| none | 1.000 ± 0.000 |

