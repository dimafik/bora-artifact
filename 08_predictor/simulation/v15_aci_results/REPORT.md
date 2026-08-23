# FX5-EXT: Adaptive Conformal Prediction under NW1 Non-Exchangeable

| Method | Coverage (mean ± std) | AUC | Mean set size |
|---|---|---:|---:|
| split_cp | 0.9453 ± 0.0109 | 0.9826 | 1.6350 |
| aci | 0.9499 ± 0.0017 | 0.9826 | 1.6421 |

**Target nominal coverage**: 0.95
**ACI gamma (learning rate)**: 0.01

**Finding**: ACI achieves nominal coverage despite NW1 non-exchangeability; split-CP undercovers.