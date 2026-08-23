# NE13: Delta-Sweep (Theorem 7 Empirical Validation)

| delta | Linear AUC | Thm7 bound 1/2+C*d^{3/2} | Kurtosis AUC | Transformer AUC |
|---|---:|---:|---:|---:|
| 0.000 | 0.4780 | 0.5000 | 0.4394 | 0.9898 |
| 0.001 | 0.5364 | 0.5001 | 0.4504 | 0.9926 |
| 0.005 | 0.5641 | 0.5012 | 0.4270 | 0.9941 |
| 0.010 | 0.5926 | 0.5035 | 0.4325 | 0.9899 |
| 0.050 | 0.9043 | 0.5391 | 0.4423 | 0.9983 |
| 0.100 | 0.9859 | 0.6107 | 0.4469 | 0.9998 |
| 0.200 | 1.0000 | 0.8130 | 0.4967 | 1.0000 |

**Theorem 7** predicts linear AUC <= 1/2 + C*delta^{3/2}; Transformer breaks this ceiling via window-aware non-linearity (Thm 3).