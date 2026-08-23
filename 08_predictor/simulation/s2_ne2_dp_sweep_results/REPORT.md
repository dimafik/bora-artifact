# NE2 (S2): Model-Extraction DP epsilon Sweep

500 queries, 30 trials per epsilon, Laplace mechanism.


| epsilon | cos-sim mean | cos-sim std |
|---|---:|---:|
| no_defense | 0.9995 | 0.0005 |
| 0.01 | 0.0393 | 0.4679 |
| 0.05 | 0.2979 | 0.4608 |
| 0.1 | 0.4601 | 0.3911 |
| 0.5 | 0.9155 | 0.0810 |
| 1.0 | 0.9694 | 0.0345 |
| 2.0 | 0.9899 | 0.0070 |
| 5.0 | 0.9981 | 0.0013 |

**Breakpoint epsilon (cos-sim < 0.5)**: 0.01