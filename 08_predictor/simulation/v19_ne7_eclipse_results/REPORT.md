# NE7: Eclipse Attack (Heilman+ USENIX Security 2015) Detection

Pattern: Eclipsed follower sees uniform RTT across all 'peers' (single adversary AS).

| Detector | AUC | Note |
|---|---:|---|
| Linear avg-RTT | 0.4883 | Eclipse undetectable by RTT magnitude alone |
| Cross-observer variance | **1.0000** | Cross-peer feature catches uniformity |
| AR(1) autocorrelation | **0.4802** | Memory-enabled detector |

**Conclusion**: Eclipse attacks are detectable by cross-observer features in the bounded blacklist advisor's window-aware predictor (Theorem 3 capacity gap empirically witnessed).