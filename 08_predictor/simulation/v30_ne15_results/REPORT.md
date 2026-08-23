# NE15: Best-Result Push

## Cross-protocol (bigger Transformer, 5 seeds)

| Protocol | mean | median | max | std |
|---|---:|---:|---:|---:|
| PBFT_MM | 0.4968 | 0.4972 | 0.5145 | 0.0125 |
| HotStuff_MM | 0.5393 | 0.7172 | 0.8343 | 0.3129 |
| Tendermint_MM | 0.5076 | 0.5038 | 0.5267 | 0.0106 |

## Ensemble on PBFT MM

| Detector | AUC |
|---|---:|
| Ensemble_AUC | 0.8166 |
| Transformer_alone_AUC | 0.4980 |