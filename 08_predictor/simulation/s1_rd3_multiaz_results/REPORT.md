# RD3: Multi-AZ Asymmetric Delay (6 nodes, 3 regions, 2 AZ)

Topology: us-east-1{a,b}, eu-west-1{a,b}, ap-northeast-1{a,c}

Asymmetric inter-region paths (±10% path bias).


| Scenario | Rounds | Succ | Ldr chg | Uniq | Byz->ldr? | median ms | p99 ms | p99 max ms |
|---|---:|---:|---:|---:|:---:|---:|---:|---:|
| vanilla | 300 | 300 | 5 | 6 | YES | 472 | 525 | 533 |
| byzantine | 300 | 253 | 4 | 5 | NO | 469 | 515 | 522 |
| ai_byzantine | 300 | 254 | 4 | 5 | NO | 465 | 524 | 554 |
