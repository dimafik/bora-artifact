# NE8m++ Adaptive Transformer Detector on PBFT MM

Closes v23 deferred work on PBFT MM hard regime.

| Detector | AUC |
|---|---:|
| Linear (v23) | 0.4911 |
| AR(1) memory (v23) | 0.5461 |
| Kurtosis (v23) | 0.5743 |
| Range/IQR (v23) | 0.5300 |
| Combined higher-order (v23) | 0.5020 |
| **TinyTransformer (v28)** | **1.0000** |

**TinyTransformer params**: 17185
**Improvement over best fixed feature (v23)**: +0.4257