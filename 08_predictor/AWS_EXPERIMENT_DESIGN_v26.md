# v26 AWS Live Experiment Design - 4 Arms Calibrated to AI Necessity Thesis

**Replaces**: v25 6-way Fabric Caliper design (AWS_5HR_EXPERIMENT_DESIGN.md)
**Thesis alignment**: Linear-Score Ceiling + Augmentation Safety + 3 operating modes

---

## 1. Hypotheses (pre-registered)

| ID | Statement | Test | alpha |
|---|---|---|---:|
| H1 | t_recover(D) < t_recover(A) on cascading 2-failure events | One-sided Wilcoxon signed-rank on paired-event recovery times | 0.001 |
| H2 | AUC_anom(D) > AUC_anom(A) + 0.15 under sophisticated Byzantine load | Paired bootstrap CI of AUC difference, 99% lower bound > 0.15 | 0.001 |
| H3 | Maintenance precision @1h horizon on top-10% predicted-degrade nodes >= 0.70 | Single-proportion Wilson 99% CI lower bound | 0.001 |
| Safety | T1/T2/T3 invariants hold in all arms (TLA+ Apalache) | Symbolic check, 0 counterexamples | n/a |

Family: 3 confirmatory tests, Holm-Bonferroni protected at alpha=0.001 each.

## 2. Four Arms

| Arm | Score head | Anomaly head | Degrade head | Implementation |
|---|:---:|:---:|:---:|---|
| A: S-Raft baseline | off | off | off | Eq.(3) Score formula only |
| B: +Prediction | on | off | off | Score_hat^{t+30s} enables pre-promote |
| C: +Anomaly | on | on | off | + blacklist on p_anom > tau_A |
| D: +Full ML | on | on | on | + maintenance warnings, full advice tuple |

Single binary, three env vars: BRAO_PREDICT, BRAO_ANOMALY, BRAO_DEGRADE.
Arms differ only in toggle state. Eliminates code-path confound.

## 3. Cluster Topology

5 S-Raft nodes (matches v5_3 SRaft_N5.cfg) across 3 AZs:
- node1 (us-east-1a, c5n.4xlarge) + sidecar
- node2 (us-east-1b, c5n.4xlarge) + sidecar
- node3 (us-east-1c, c5n.4xlarge) + sidecar
- node4 (us-east-1a, c5n.4xlarge) + sidecar
- node5 (us-east-1b, c5n.4xlarge) + sidecar
- injector (us-east-1b, t3.large): failure scheduler + Byzantine generator + GC injector

intra-region <=2ms RTT.

## 4. Workload + Injection Protocol

### 4.1 Steady-state workload
100 req/s mixed read/write through S-Raft client API.

### 4.2 Cascading-failure injections (all 4 arms, identical schedule)
100 events per arm. Each event:
1. SIGKILL leader (node-X)
2. Wait tau in [40, 120] ms
3. SIGKILL primary (node-Y)
4. Measure recovery_time = t_committed_after - t_leader_killed
5. SSH revive both, 30s drain

Schedule: every 30s for 50 min = 100 events per arm.
Same seed across arms -> paired design.

### 4.3 Byzantine traffic overlay (last 10 min of each arm)
1 sophisticated-Byzantine node:
- ACK at exact mean latency of legit cluster
- RTT matches legit mean & std
- Skips ~30% of actual commits silently

Ground truth: this node IS Byzantine. Anomaly head must flag it.

### 4.4 GC-stall injections (middle 20 min)
SSM RunCommand schedules 5 synthetic GC stalls per node:
- Duration: 600-1500 ms (uniform random)
- Arrival: random within 20-min window

Hardware counters scraped -> degrade head input.
Ground truth: 1h-ahead label = 1 if any stall in next 60 min.

## 5. Timeline (5 hours)

```
T+0:00 - 0:10  Provision (Terraform apply, 6 VMs)
T+0:10 - 0:25  S-Raft bootstrap
T+0:25 - 0:35  Calibration (chrony, sanity, healthz)

T+0:35 - 1:25  Arm A: baseline (50 min, 100 injections)
T+1:25 - 1:30  Toggle: enable predict; rolling restart
T+1:30 - 2:20  Arm B: +Prediction
T+2:20 - 2:25  Toggle: enable anomaly
T+2:25 - 3:15  Arm C: +Anomaly (+ Byzantine overlay last 10 min)
T+3:15 - 3:20  Toggle: enable degrade
T+3:20 - 4:10  Arm D: +Full ML (+ Byzantine overlay last 10 min)
T+4:10 - 4:40  Analysis pipeline
T+4:40 - 5:00  Teardown
```

400 paired events across 4 arms for H1.

## 6. Statistical Analysis

### 6.1 H1: Recovery time
Paired design (event k uses same RNG seed across arms).
One-sided Wilcoxon signed-rank on {R_k(A) - R_k(D)}, H1: median > 0.
Effect size: median paired difference + Hodges-Lehmann 99% CI.

### 6.2 H2: Anomaly AUC under live Byzantine
Per-window anomaly scores. Arm A: best univariate detector (post-hoc).
Arm D: ML head.
Paired bootstrap (10,000 resamples) of AUC diff, 99% LB > 0.15.

### 6.3 H3: Maintenance precision
Top-10% predicted-degrade nodes per 10-min window from Arm D degrade head.
Compare to ground truth (GC stall in next 1h).
Wilson 99% CI lower bound >= 0.70.

### 6.4 Holm-Bonferroni family
3 tests at alpha=0.001 each. Adjusted thresholds {0.000333, 0.0005, 0.001}.

## 7. Updated Cost Estimate

```
6 x c5n.4xlarge x 5h x $0.864/hr     = $25.92
1 x t3.large x 5h x $0.0832/hr       = $ 0.42
EBS gp3                               = $ 0.66
Cross-AZ data transfer (est.)         = $ 0.40
Internet egress (5 GB)                = $ 0.45
S3 PUT + 1mo storage                  = $ 0.13
CloudWatch                            = $ 0.02
-----------------------------------------------
TOTAL                                 ~ $28.00
```

Within $35 soft cap.

## 8. Pre-Registration Diff

New runbook files to add before fresh OTS stamp:
1. runbook/scripts/run_orchestrator_v26.sh (4-arm scheduling)
2. runbook/caliper/benchmark-arm-{a,b,c,d}.yaml (S-Raft client workload)
3. runbook/analysis/aws_v26_analysis.py (H1-H3 tests)
4. runbook/scripts/failure_injector.py
5. runbook/scripts/byzantine_overlay.py

Then: bash scripts/preregister.sh > preregister.hash; ots stamp.

## 9. What This Experiment Proves

Proves (if all hypotheses confirmed):
- H1: ML reduces cascading recovery time in live AWS deployment
- H2: ML breaks AUC ceiling on live Byzantine attacks (not just simulator)
- H3: ML enables 1h-ahead maintenance with operational-grade precision

Doesn't prove:
- Multi-region (single us-east-1)
- Adversary classes other than the calibrated sophisticated one
- Long-tail P99.99 (5h is medium-duration)

Honest framing for manuscript: live AWS validation under one canonical
sophisticated attacker. Generalisation is future work.

## 10. Sign-off

7-expert panel signs off when this design + the runbook files above
are written and the pre-register hash is freshly OTS-anchored.
