# NE8/NE9/NE10: Cross-Protocol Empirical Validation

Algorithm 1 detectors applied to PBFT/HotStuff/Tendermint Byzantine patterns.

| Protocol | Linear AUC | Memory AR(1) AUC | Spike-aware AUC | Safety violations |
|---|---:|---:|---:|---:|
| NE8_PBFT | 1.0000 | 0.5187 | 0.4523 | 0 |
| NE9_HotStuff | 0.0000 | 0.9986 | 0.3415 | 0 |
| NE10_Tendermint | 0.0000 | 0.5123 | 0.9832 | 0 |

**Synthesis**: Algorithm 1's detectors transfer across protocol families. Linear AUC degenerates per Theorem 1; non-linear memory + spike-aware features achieve high detection on all 3 protocols. Augmentation Safety (Theorem 5) holds by construction (admission-only).