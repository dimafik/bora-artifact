# PATE-style DP: Pareto Recovery

K=10 teachers on disjoint shards; noisy majority vote per query.

| epsilon | attacker cos-sim | legit AUC | gap |
|---|---:|---:|---:|
| no_defense_naive | 0.9995 | 1.0000 | +0.0005 |
| 0.01 | 0.4010 | 0.9998 | +0.5988 |
| 0.05 | 0.9301 | 0.9998 | +0.0697 |
| 0.1 | 0.9801 | 0.9998 | +0.0196 |
| 0.5 | 0.9990 | 0.9999 | +0.0008 |
| 1.0 | 0.9994 | 0.9998 | +0.0004 |
| 2.0 | 0.9992 | 0.9998 | +0.0006 |
| 5.0 | 0.9993 | 0.9998 | +0.0005 |

**Pareto-optimal**: epsilon = 0.01, gap = +0.5988

**Comparison vs naive Laplace DP (v14)**: PATE preserves legit AUC at much higher level for the same attacker block.