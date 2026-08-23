# v28 Real Multi-Process Raft Deployment Results

Each row = real 5-node Raft cluster running for given duration with actual TCP sockets, election timers, and heartbeats.

| Scenario | Elections | Leader changes | Blacklist events | Byz advice rejected | Unique leaders | Byz was leader? | Median p99 RTT (ms) |
|---|---:|---:|---:|---:|---:|:---:|---:|
| vanilla | 579 | 0 | 0 | 0 | 1 | NO | 16.08 |
| byzantine | 580 | 0 | 0 | 0 | 1 | NO | 18.93 |
| ai_byzantine | 575 | 0 | 0 | 0 | 1 | NO | 16.10 |
