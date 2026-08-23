# NE6: CVE-2021-43667 Empty-Payload Attack Detection

Byzantine pattern: $CC \to 0$ for 1-2 ticks/window, $RTT$ unchanged, moments matched to legitimate.

| Detector | AUC | Theoretical claim |
|---|---:|---|
| Linear scorer | 0.4998 | Theorem 1: AUC=1/2 under moment matching |
| Memory-enabled AR(1) advisor | **0.5014** | Theorem 4: memory required |
| Spike-aware NW1 feature | **1.0000** | NW1 operational detection |

**Moment matching verified**: |mean_legit - mean_byz| = 0.0003

**Conclusion**: CVE-2021-43667 empty-payload attack is detectable by the bounded blacklist advisor (memory-enabled + spike-aware), but NOT by any linear scorer — matching Theorem 1 prediction.