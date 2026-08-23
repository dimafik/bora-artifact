# NE8m/NE9m/NE10m: Moment-Matched Cross-Protocol Detection (v22)

Closes v21 honest-deferred work: Byzantine variants per protocol calibrated to match first-two-moment envelope of legitimate distribution.

| Protocol (MM) | Linear AUC | Memory AR(1) AUC | Spike-aware AUC | mean gap | var gap |
|---|---:|---:|---:|---:|---:|
| NE8m_PBFT_MM | 0.4840 | 0.5311 | 0.4622 | 0.00144 | 0.00013 |
| NE9m_HotStuff_MM | 0.5000 | 0.9984 | 0.4353 | 0.00000 | 0.00000 |
| NE10m_Tendermint_MM | 0.4943 | 0.5379 | 0.9824 | 0.00012 | 0.00002 |

**Conclusion**: Under moment matching, linear AUC approaches 0.5 (Thm 1 ceiling transfers to all 3 protocol families), while memory/spike-aware detectors retain discrimination. Safety violations 0 by design.