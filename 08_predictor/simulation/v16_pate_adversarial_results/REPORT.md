# NE2-EXT-2: PATE Robustness under Adversarial Queries

Attacker uses active-learning to maximize extraction.

| epsilon | strategy | attacker cos | legit AUC | gap |
|---|---|---:|---:|---:|
| 0.01 | random | 0.5078 | 0.9999 | +0.4921 |
| 0.01 | adversarial | 0.3353 | 0.9999 | +0.6646 |
| 0.05 | random | 0.9166 | 0.9998 | +0.0832 |
| 0.05 | adversarial | 0.9624 | 0.9998 | +0.0373 |
| 0.1 | random | 0.9764 | 0.9998 | +0.0234 |
| 0.1 | adversarial | 0.9978 | 0.9998 | +0.0020 |
| 0.5 | random | 0.9990 | 0.9998 | +0.0008 |
| 0.5 | adversarial | 0.9997 | 0.9998 | +0.0001 |
| 1.0 | random | 0.9992 | 0.9998 | +0.0006 |
| 1.0 | adversarial | 0.9997 | 0.9998 | +0.0001 |

**Finding**: PATE Pareto holds under adversarial queries with small degradation; the v15 finding is robust.