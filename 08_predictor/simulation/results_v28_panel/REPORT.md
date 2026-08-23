# v28 7-Expert Panel-Consensus Experiments (Blacklist-Only Model, 24-Channel Telemetry)

**Seeds**: 30  •  **Channels**: 24  •  **Window**: 64

## L1 — Liveness Stress (Raft expert)

| $|B|/(f-1)$ | FP rate | TP rate | Liveness OK |
|---:|---:|---:|---:|
| 0.0 | 0.0000 | 1.0000 | 1.00 |
| 0.2 | 0.0000 | 1.0000 | 1.00 |
| 0.4 | 0.0000 | 1.0000 | 0.00 |
| 0.6 | 0.0000 | 0.9950 | 0.00 |
| 0.8 | 0.0000 | 0.9956 | 0.00 |
| 1.0 | 0.0000 | 0.9967 | 0.00 |

## C1 — Refined Theorem 1 Tightness (TNSE Best Award)

| δ | Empirical AUC | Theory Φ(δ/√2) | Abs error |
|---:|---:|---:|---:|
| 0.00 | 0.5730 | 0.5000 | 0.0730 |
| 0.02 | 0.5734 | 0.5056 | 0.0677 |
| 0.04 | 0.5737 | 0.5113 | 0.0624 |
| 0.06 | 0.5741 | 0.5169 | 0.0572 |
| 0.08 | 0.5746 | 0.5226 | 0.0520 |
| 0.10 | 0.5750 | 0.5282 | 0.0468 |
| 0.15 | 0.5762 | 0.5422 | 0.0340 |
| 0.20 | 0.5774 | 0.5562 | 0.0212 |
| 0.30 | 0.5801 | 0.5840 | 0.0039 |
| 0.50 | 0.5877 | 0.6382 | 0.0504 |
| 0.75 | 0.6021 | 0.7021 | 0.1000 |
| 1.00 | 0.6199 | 0.7602 | 0.1404 |

## N1 — Asymmetric Multi-AZ (Distributed systems)

| AZ ratio | FP (high-AZ legit) | FP (base-AZ legit) |
|---:|---:|---:|
| 1.0 | 0.0000 | 0.0000 |
| 2.0 | 0.0000 | 0.0000 |
| 3.0 | 0.0000 | 0.0000 |
| 5.0 | 0.0000 | 0.0000 |
| 8.0 | 0.0000 | 0.0000 |
| 12.0 | 0.0000 | 0.0000 |

## B1 — Predictor Calibration (AI expert)

| $\rho_{AR}$ | ECE | Brier |
|---:|---:|---:|
| 0.0 | 0.4070 | 0.3297 |
| 0.2 | 0.3896 | 0.3025 |
| 0.4 | 0.3914 | 0.2466 |
| 0.6 | 0.3545 | 0.1936 |
| 0.8 | 0.3143 | 0.1473 |

## C2 — Adaptive Moment-Matching Adversary (Algorithms expert)

| Slack ε | Memory-enabled AUC |
|---:|---:|
| 0.00 | 1.0000 ± 0.0000 |
| 0.02 | 1.0000 ± 0.0000 |
| 0.05 | 1.0000 ± 0.0000 |
| 0.10 | 1.0000 ± 0.0000 |
| 0.20 | 1.0000 ± 0.0000 |
| 0.30 | 1.0000 ± 0.0000 |

## C3 — Joint M+B+S Attack (Theoretical IB)

- Linear detector AUC: **0.8617 ± 0.0478**
- Memory-enabled detector AUC: **0.7240 ± 0.0092**

## O1 — Mean Time Between False Demotions (Blockchain expert)

- False-positive flags per seed (2,000 benign ticks): **0.00 ± 0.00**
- MTBFD: **inf ticks** (= infs at 50 ms heartbeat)
