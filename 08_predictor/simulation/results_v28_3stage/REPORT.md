# v28 3-Stage Hybrid Evaluation Report (Consistency-Robustness)

Stage 1: theoretical-limit verification on D1 synthetic — already covered by E1-E6 + L1-O1 (18 experiments). Stage 2/3 results below.

## Stage 2A — Packet-Loss × Jitter Sweep

| Loss | Jitter | Failover (vanilla) | Failover (AI-aug) | Storm (van) | Storm (AI) |
|---:|---:|---:|---:|---:|---:|
| 0.00% | 1 ms | 262 ms | 146 ms | 0.00% | 0.00% |
| 0.00% | 5 ms | 262 ms | 146 ms | 0.00% | 0.00% |
| 0.00% | 10 ms | 262 ms | 146 ms | 0.00% | 0.00% |
| 0.00% | 20 ms | 262 ms | 147 ms | 0.00% | 0.00% |
| 0.00% | 30 ms | 263 ms | 146 ms | 0.00% | 0.00% |
| 1.00% | 1 ms | 261 ms | 146 ms | 0.77% | 0.17% |
| 1.00% | 5 ms | 261 ms | 146 ms | 0.77% | 0.17% |
| 1.00% | 10 ms | 261 ms | 147 ms | 0.77% | 0.17% |
| 1.00% | 20 ms | 262 ms | 147 ms | 0.77% | 0.17% |
| 1.00% | 30 ms | 262 ms | 146 ms | 0.77% | 0.17% |
| 2.00% | 1 ms | 262 ms | 147 ms | 1.70% | 0.37% |
| 2.00% | 5 ms | 262 ms | 147 ms | 1.70% | 0.37% |
| 2.00% | 10 ms | 263 ms | 147 ms | 1.70% | 0.37% |
| 2.00% | 20 ms | 263 ms | 147 ms | 1.70% | 0.37% |
| 2.00% | 30 ms | 263 ms | 147 ms | 1.70% | 0.37% |
| 3.00% | 1 ms | 262 ms | 147 ms | 2.90% | 0.47% |
| 3.00% | 5 ms | 263 ms | 147 ms | 2.90% | 0.47% |
| 3.00% | 10 ms | 263 ms | 147 ms | 2.90% | 0.47% |
| 3.00% | 20 ms | 263 ms | 147 ms | 2.90% | 0.47% |
| 3.00% | 30 ms | 264 ms | 147 ms | 2.90% | 0.47% |
| 5.00% | 1 ms | 265 ms | 147 ms | 4.73% | 0.73% |
| 5.00% | 5 ms | 265 ms | 147 ms | 4.73% | 0.73% |
| 5.00% | 10 ms | 265 ms | 146 ms | 4.73% | 0.73% |
| 5.00% | 20 ms | 264 ms | 147 ms | 4.73% | 0.73% |
| 5.00% | 30 ms | 265 ms | 147 ms | 4.73% | 0.73% |

## Stage 2B — Telemetry-Manipulation Detection AUC

| Loss | Jitter | AUC mean ± std |
|---:|---:|---:|
| 0.00% | 1 ms | 0.998 ± 0.001 |
| 0.00% | 10 ms | 0.770 ± 0.012 |
| 0.00% | 30 ms | 0.518 ± 0.012 |
| 2.00% | 1 ms | 0.961 ± 0.006 |
| 2.00% | 10 ms | 0.731 ± 0.014 |
| 2.00% | 30 ms | 0.518 ± 0.010 |
| 5.00% | 1 ms | 0.882 ± 0.011 |
| 5.00% | 10 ms | 0.681 ± 0.013 |
| 5.00% | 30 ms | 0.516 ± 0.009 |

## Stage 2C — Consistency-Robustness Curve

| Pred AUC | System gain (failover %) | Safety violations |
|---:|---:|---:|
| 0.00 | -0.19% | 0 |
| 0.20 | -0.19% | 0 |
| 0.50 | -0.19% | 0 |
| 0.80 | 35.88% | 0 |
| 0.95 | 53.91% | 0 |
| 1.00 | 59.93% | 0 |

## Stage 3A — TPS-Latency Pareto (vs. SmartBFT-equivalent)

| TPS | Median (vanilla) | Median (AI) | Median (BFT-eq) | p99 (van) | p99 (AI) | p99 (BFT-eq) |
|---:|---:|---:|---:|---:|---:|---:|
| 100 | 6.42 | 6.18 | 8.66 | 14.05 | 13.74 | 18.41 |
| 250 | 6.42 | 6.18 | 8.66 | 14.05 | 13.74 | 18.41 |
| 500 | 6.42 | 6.18 | 8.66 | 14.05 | 13.74 | 18.41 |
| 1000 | 6.42 | 6.18 | 8.66 | 14.05 | 13.74 | 18.41 |
| 1500 | 6.42 | 6.18 | 8.66 | 14.05 | 13.74 | 18.41 |
| 2000 | 8.55 | 8.24 | 11.55 | 18.74 | 18.33 | 24.54 |

## Stage 3B — Safety under Distribution-Robust Stress (DRS)

- Total advice events: **30000**
- Total safety violations: **0**
- Fail-open engagements: **8608**
- Violations per attack mode: {'noisy': 0, 'wrong': 0, 'max_out': 0}

Theorem~5's safety guarantee holds across all three adversarial-predictor modes (noisy/wrong/max_out): zero violations across $30{,}000$ events.
