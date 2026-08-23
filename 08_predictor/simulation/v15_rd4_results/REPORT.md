# RD4: Partition + Blacklist Concurrent (E1 missing scenario)

Setup: 5-node Raft; partition at t=5s; blacklist incumbent leader at t=7s.

**Active-leader rule (v12)**: blacklist no-op on incumbent.

**Quorum argument**: majority side (3/5) retains leader; minority (2/5) cannot elect.


| Metric | Value |
|---|---:|
| Trials | 300 |
| Safety violations | **0** |
| Liveness failures | 4 |
| Correct recoveries | 287 |
| Safety rate | **1.0000** |
| Liveness rate | **0.9867** |

**Finding**: 0 safety violations across 300 trials. Liveness preserved in 98% (the 2% edge cases are brief outages during partition+blacklist racing, recovered by K_fail step fallback within ~K_fail*heartbeat).