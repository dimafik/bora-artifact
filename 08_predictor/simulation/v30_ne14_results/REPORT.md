# NE14: Adversarial-Trained Transformer Defense

params: 58577

Static (defended): AUC = 0.4811

| PGD eps | AUC |
|---|---:|
| 0.05 | 0.5058 |
| 0.1 | 0.5058 |
| 0.2 | 0.5058 |
| 0.3 | 0.5058 |

**Comparison vs v29 NE11**: NE11 undefended AUC=0.821 under PGD; NE14 defended AUC reported above.