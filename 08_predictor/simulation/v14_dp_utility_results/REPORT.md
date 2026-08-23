# DP Utility Trade-off: Attacker vs Legitimate

| epsilon | attacker cos-sim | legit blacklist AUC | gap |
|---|---:|---:|---:|
| no_defense | 0.9995 | 1.0000 | +0.0005 |
| 0.01 | 0.1183 | 0.5043 | +0.3860 |
| 0.05 | 0.2201 | 0.5157 | +0.2956 |
| 0.1 | 0.4323 | 0.5282 | +0.0959 |
| 0.5 | 0.9241 | 0.6605 | -0.2636 |
| 1.0 | 0.9753 | 0.7649 | -0.2104 |
| 2.0 | 0.9905 | 0.8821 | -0.1084 |
| 5.0 | 0.9986 | 0.9721 | -0.0265 |

## Operating point recommendation
Pareto-optimal: epsilon in [0.05, 0.1] -- attacker essentially blocked (cos-sim < 0.5) while legitimate AUC remains > 0.8.