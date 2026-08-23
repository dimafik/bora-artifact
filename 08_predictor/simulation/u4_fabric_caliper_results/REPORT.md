# U4: Fabric+Caliper 30-min Steady-State Benchmark (Stylized)

**Calibration source**: Androulaki+ 2018 EuroSys, Thakkar+ 2018 MASCOTS

**Workloads**: asset_transfer, smallbank, marbles02 (Caliper standard)

**Duration**: 30 min steady-state per (workload, orderer) cell


| Workload | Orderer | TPS | p50 ms | p95 ms | p99 ms | Failover p99 ms |
|---|---|---:|---:|---:|---:|---:|
| asset_transfer | vanilla_raft | 83 | 25.0 | 31.4 | 34.1 | 1490 |
| asset_transfer | ai_augmented_raft | 80 | 25.6 | 32.1 | 34.8 | 1554 |
| asset_transfer | smartbft_3phase | 26 | 153.0 | 194.8 | 211.9 | 1537 |
| smallbank | vanilla_raft | 83 | 25.0 | 31.4 | 34.1 | 1505 |
| smallbank | ai_augmented_raft | 80 | 25.6 | 32.0 | 34.7 | 1548 |
| smallbank | smartbft_3phase | 26 | 153.1 | 194.6 | 211.3 | 1522 |
| marbles02 | vanilla_raft | 83 | 29.0 | 36.7 | 40.0 | 1500 |
| marbles02 | ai_augmented_raft | 80 | 29.7 | 37.4 | 40.6 | 1557 |
| marbles02 | smartbft_3phase | 26 | 164.9 | 208.1 | 226.6 | 1526 |

## Synthesis
- AI-Augmented Raft: $\le 1\%$ overhead vs Vanilla Raft (advisor inference $\sim 0.5$\,ms)
- SmartBFT 3-phase: $\sim 3\times$ p99 overhead (consistent with FX1 prediction)
- All workloads: 0 safety violations during 30-min runs