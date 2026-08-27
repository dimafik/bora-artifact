# 12 — What a degraded *leader* costs (campaigns R25C and R25D)

Answers Reviewer 2, point 5: *"It is not yet convincingly demonstrated that this
translates into sufficiently broad system-level benefit."*

BORA keeps a degraded orderer out of the candidate pool. Until this campaign the
manuscript never measured what that prevents. It reported a **single run**
(`r25b_20260810-233812`, N=5): 467.8 → 127.5 tx/s, 99.6% of transactions failed.
This campaign replaces that one run with 36 pre-registered ones.

---

## What was run

Four arms, back to back on one cluster, so the comparison is paired inside each
run. Each arm is a Caliper sweep at 100/200/300/400/500 tx/s, 30 s per rate.

| arm | condition |
|---|---|
| `C_clean` | no delay, whoever leads — **the baseline this run is judged against** |
| `F_follower` | orderer3 delayed, a healthy node leads |
| `L_leader` | orderer3 delayed **and** pinned into the leader role |
| `C_clean_post` | no delay again, end of run — the bracket |

Cluster: the standing 7-consenter `mychannel`, Fabric v3.1.4, single host.
Delay: `+200 ms` on orderer3 via pumba/netem. Pinning: up to 40 incumbent
restarts with the delay **off**, because a delayed node is less likely to win.

`+200 ms` rather than more is deliberate and is explained in the harness: at
2 s the leader's heartbeats approach the ~5 s election timeout and the degraded
leader is deposed within seconds, which destroys the condition being measured.

---

## Results

**25 runs whose own clean arm verified at ≥ 450 tx/s** (see *Caveat* below):

| quantity | value |
|---|---|
| throughput with a degraded **leader** | median **35%** of that run's baseline — a **65% loss** |
| throughput with a degraded **follower** | 79% of baseline — a **21% loss** |
| **asymmetry** | **3.2×** |
| mean latency | **27× higher** |
| leadership | orderer3 held it start to finish in **all 25** runs |

Pre-registered primary of R25D, over all 36 runs as registered:

    13/36 = 36.1% of runs had not recovered when the sweep ended
            95% Wilson CI [22.5%, 52.4%]
    restricted to the 25 verified-baseline runs: 8/25 = 32.0% [17.2%, 51.6%]

The two agree well inside their intervals.

### The cost is a recovery time, not a fixed penalty

This is the finding that changed how the result is described. Reading the whole
sweep instead of only its last point:

- **Every run starts alike.** At 100 tx/s all 25 fail 45–60% of submissions; at
  200 tx/s all fail 76–89%. The groups are indistinguishable there.
- **They diverge at 300 tx/s**, where 17 runs drop to 10–27% failure and 8 stay
  at 88–89%.
- **The divergence point itself varies.** One run recovered at 400 tx/s, another
  only at 500. The apparent gap at 500 tx/s exists because the sweep stops there.

So the eight "stalling" runs are not a separate failure mode. They are the runs
that had **not yet escaped the backlog when the sweep ended** after 150 s of
load. Their arm also ran longer: 719 s median against 594 s.

Once a run escapes it commits almost exactly **one third** of the offered rate
(100.0, 133.3, 166.7 at 300/400/500); one that does not sits near **2/9**
(67, 89, 113).

### The failures are real, not a measurement artefact

`belowceiling-sweep.yaml` warns that a saturated cluster can make Caliper report
`Succ:0` while the ledger commits anyway. That is **not** what happened here.
Block production matches the reported successes in both groups:

| | Caliper successes | blocks committed | tx/block | blocks/s |
|---|---:|---:|---:|---:|
| clean | 45,020 | 4,504 | 9.99 | 20.6 |
| recovered | 33,339 | 7,246 | 4.60 | 12.1 |
| did not recover | 7,250 | 3,578 | 2.02 | 4.97 |

`blocks × tx/block ≈ successes` in every row, so the failed transactions never
reached the ledger. The mechanism is visible in the same table: a delayed leader
cuts blocks on `BatchTimeout` rather than on `BatchSize`, so blocks get smaller
*and* rarer, and the two effects multiply.

### Aftermath

Runs that fail fast leave no queue and return to baseline at once (median
`D` = 1.00). Runs that succeed slowly accumulate a backlog that holds the channel
near **44%** of baseline for minutes after the delay is removed (median
`D` = 0.44). The less catastrophic mode is the one whose damage outlasts the
attack.

---

## Caveat: the testbed degraded partway through, and the clean arm caught it

Because every run carries its own baseline, this was visible rather than silent:

    runs  1–23  C_clean at 500 tx/s = 468 tx/s (±1, on 23 consecutive runs)
    runs 24–36  mostly 202–223, with two runs still at 468 and 461

Cause: ledger size. Correlating each run's starting block height against its
clean baseline gives **r = −0.746**, with a threshold near 570,000 blocks. The
channel began at height 3,650 and ended at 905,020; each orderer's ledger
directory reached 36 GB.

This is **not repairable by re-running** — the ledger only grows, so repeats
would start deeper into the collapsed regime. It is handled by reporting both
the registered 36-run analysis and the 25-run restriction, which agree.

Full detail: `prereg/PREREG_R25D_ADDENDUM_01.md`.

---

## Layout

| path | contents |
|---|---|
| `prereg/` | both pre-registrations, their SHA-256 records, and three addenda. The harness hash is identical across R25C and R25D, which is what justifies pooling |
| `harness/` | `r25_leader_cost3.sh` (the measurement), plus the warm-up guard and the detached supervisor that drove the campaign |
| `runs/` | `summary.txt` and `arms.csv` for **all 48 attempts**, valid and invalid alike |
| `evidence/` | two complete runs including full Caliper logs — one that recovered, one that did not — so the ledger-versus-successes check can be repeated |
| `analysis/` | the analysis scripts, each written **before** the data it reads |
| `results/per_run_metrics.csv` | one row per attempt, every arm × rate, with the derived `R`, `Rf`, failure fraction and drift |

Bulk Caliper logs for the other 46 attempts (~6.5 MB each) stay in
`D:\fabric-d2\results\r25c_*` and are not duplicated here.

### Invalid attempts

12 of the 48 produced no measurement, and none produced a wrong number — the
harness's ledger-delta check refused every one. Ten were the anchor-peer failure
of `PREREG_R25C_ADDENDUM_02.md`: the channel had no anchor peers, so Caliper's
service discovery could not assemble an endorsing pair and every transaction
failed. One was the same defect before it was diagnosed, and one was interrupted
mid-run.
