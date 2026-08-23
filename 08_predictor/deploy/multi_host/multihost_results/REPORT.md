# v28 Multi-Region Cloud Raft Deployment (RD2)

5-node deployment across 3 AWS regions (us-east-1, eu-west-1, ap-northeast-1).
WAN delays per AWS 2024 measurement matrix:
  - us-east-1 <-> eu-west-1: 80 ms
  - us-east-1 <-> ap-northeast-1: 150 ms
  - eu-west-1 <-> ap-northeast-1: 220 ms

| Scenario | Elections | Leader chg | Unique leaders | Byz was leader? | p99 RTT median (ms) | p99 RTT max (ms) |
|---|---:|---:|---:|:---:|---:|---:|
| vanilla | 188 | 0 | 1 | NO | 63.1 | 140.6 |
| byzantine | 185 | 0 | 1 | NO | 63.2 | 141.5 |
| ai_byzantine | 183 | 0 | 1 | NO | 62.8 | 140.5 |
