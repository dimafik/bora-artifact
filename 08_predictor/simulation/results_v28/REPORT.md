# v28 D1 Synthetic Separation Results

**Seeds**: 30  •  **Per-class size**: 1500  •  **Window length default**: 64

## RQ1 — Linear-Score Non-Identifiability (Theorem 1)

Detector AUC against each attacker class, mean across seeds:

| Attack | Linear (instant) | Static-Univariate (window) | Memory-Enabled (autocorr) |
|---|---:|---:|---:|
| moment-matching | 0.508 | 0.512 | 1.000 |
| burst-delay | 0.764 | 1.000 | 0.805 |
| selective-lag | 0.980 | 0.509 | 0.514 |

AUC reported is `max(AUC, 1-AUC)` — the operational best-direction AUC, since a linear / univariate static scorer has no fixed sign convention against an adversarial class.  Under `moment-matching` with a stationary legit distribution (Theorem 1's exact regime), both linear and static-univariate detectors collapse to ~ 0.5 as predicted, while the autocorrelation-based memory-enabled detector breaks the ceiling.

## RQ2 — Static Regret in Switching Regimes (Theorem 2)

| Regime-switch prob ρ | Static linear regret (mean) |
|---:|---:|
| 0.00 | 0.0021 |
| 0.05 | 0.0022 |
| 0.10 | 0.0022 |
| 0.20 | 0.0021 |

## RQ3 — Information Capacity Gap (Theorem 3)

| Attack | I(score_linear; y) | I(score_memory; y) | Gap |
|---|---:|---:|---:|
| burst-delay | 0.0066 | 0.4009 | 0.3943 |
| moment-matching | 0.2095 | 0.6931 | 0.4836 |
| selective-lag | 0.4152 | 0.0049 | -0.4103 |

## RQ4 — Memory Necessity (Theorem 4)

| Window length W | Memory-enabled AUC (moment-matching) |
|---:|---:|
| 1.0 | 0.500 ± 0.010 |
| 8.0 | 0.978 ± 0.002 |
| 32.0 | 1.000 ± 0.000 |
| 64.0 | 1.000 ± 0.000 |
| 128.0 | 1.000 ± 0.000 |

AUC rises monotonically from 0.5 at W=1 (memoryless) towards 1 as W grows, confirming Theorem 4.

## RQ5 — Augmentation Safety (Theorem 5)

Across 400 simulated advice events, observed safety violations: **0** — Algorithm 1 preserves the base protocol's safety invariants by construction.

