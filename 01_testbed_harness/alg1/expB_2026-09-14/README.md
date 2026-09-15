# expB_2026-09-14 — Experiment B: six runs, no reportable result

**Nothing in the manuscript rests on this directory.** Section V-D stands as
submitted. This is kept because the project keeps discarded runs together with
the reason they were discarded, and because the reason turned out to be the same
one in every run.

## What was asked

Section V-D answers R2-5 with two separately measured quantities: how often the
unguarded arm seats the degraded orderer (21 of 240 forced elections at
+200 ms), and what a degraded leader costs (a median 35% of that run's own clean
baseline). **The paper reports them side by side, and does not multiply them.**

Experiment B asked whether the combined effect could be measured directly
instead — one continuous load, forced elections underneath, vanilla against
guarded — so the answer would be a single observed aggregate rather than two
numbers a reader combines. Six runs over two days. It could not.

## The defect that runs through all of it

Every run here offers 300 tx/s. On this rig that is fine when nothing is
delayed, and past the knee as soon as one orderer is:

| condition (60 s, no elections, o3 a follower) | committed | failed |
|---|---|---|
| clean | 18,008 | **0** |
| +200 ms on orderer3 | 5,745 | **12,263** |

That is `evidence/04_isolation_no_elections/`, and as first written this section
read it as: a single delayed follower takes the cluster from a 0% failure rate to
**68%** at this offered rate, before any election is forced.

**Correction (2026-09-16).** That reading does not hold. Run 04 did not read the
qdisc back, and `scripts/expB_arms.sh`, written after it, records the 68% as a
default-queue (limit 1000) result, where the injected fault is delay *and* loss;
run 04 is void as a measure of delay. The campaign in 06 set `limit 10000`, and
its 59–65% failure rate is set by the forced-election duty cycle (an 11 s pause
every 30–40 s; commit rate 27–60 tx/s inside a pause, 190–207 tx/s between
pauses), not by the delayed follower: the guarded arms, in which orderer 3 never
led, fail at the same rate. The limit-10000 re-calibration transcripts behind the
0.14% and the 5,663/5,713 figures in `expB_arms.sh` were not preserved. What
stands is that every arm below drops most of its offered load, so the throughput
comparison inherits that variance.

The same defect voided the first `11_potency` re-measurement at 300 tx/s, where
it was caught from the failure counts and fixed by dropping to 150 tx/s. It was
never carried back to Experiment B. Had it been, these runs would have been
re-run at an operating point every condition sustains before any of their
numbers were read.

## Run by run

### `evidence/01_singlehost_pilot_no_anchors/` — nothing committed

The ledger never moved. Every transaction failed with

```
EndorseError: 9 FAILED_PRECONDITION: no combination of peers can be derived
which satisfy the endorsement policy
```

**Cause: no anchor peers.** The Caliper network config uses `discover: true`,
and service discovery cannot find another organisation's endorsers unless that
organisation has an anchor peer in the channel config. `nsweep_bringup.sh` never
sets one, because the leadership experiments it was written for endorse nothing.
`_set_anchors.sh` exists for exactly this and its header describes this failure;
the pilot simply did not call it.

The election columns survive: with `B_t = []` the target took leadership **3 of
10**, with `B_t = [3]` **0 of 10**. Consistent with Section V-C, far too small to
report, and void as a throughput measurement.

### `evidence/02_singlehost_pilot/` — committed, comparison empty

```
arm,height_start,height_end,blocks,seconds,blocks_per_s,target_terms
vanilla,207,4035,3828,188,20.3617,0
guarded,4972,8208,3236,185,17.4919,0
```

Three faults, all of design rather than of the system:

1. **The target never led in the unguarded arm** (`target_terms = 0`), so the
   guard had nothing to prevent and the two arms measured the same situation
   twice.
2. **The arms ran on very different ledger sizes** (207→4,035 against
   4,972→8,208). Section V-D already records mid-campaign ledger growth as a
   confound on this testbed; this reproduced it.
3. **The noise exceeds the effect sought.** Per-election block counts vary with
   a coefficient of 50% (vanilla) and 26% (guarded), and the arms sit 14% apart,
   against an expected effect near 6%.

Both single-host runs use `createAsset.js`, which mints a fresh key per
transaction, so the world state grows without limit for as long as the campaign
runs.

### `evidence/03_xhost_pilot_default_queue/` — cross-host, contaminated injection

```
arm,height_start,height_end,blocks,seconds,target_terms,elections
vanilla,18392,31201,12809,1857,4,40
guarded,33456,41101,7645,1955,0,40
```

6.90 against 3.91 blocks/s, a 43% gap in the guard's disfavour — and not a
measurement of the guard. This run used `netem`'s **default queue of 1000
packets**. A queue that size holds `rate x delay` packets in flight, so above
roughly `limit / delay` per second it overflows and netem **drops**; at 300 tx/s
with a 200 ms delay the rule silently became "delay and heavy loss" rather than
delay. Re-calibrated with `limit 10000`, the same injection costs a delayed
*follower* **0.14%** instead of the 68% this run's conditions implied (that
re-calibration transcript was not preserved; see the correction at the top).

The campaign runs set `limit 10000` explicitly; run 04 did not read the qdisc back.

### `evidence/04_isolation_no_elections/` — the control, and it is not clean either

Three conditions, three repetitions, no elections, orderer2 leading throughout so
that orderer3 is a follower in every condition and the guard should therefore do
nothing:

| | r1 | r2 | r3 | mean |
|---|---|---|---|---|
| A clean | 18,008 | 18,008 | 18,008 | 18,008 |
| B +200 ms, `B_t = []` | 5,745 | 5,806 | 5,868 | 5,806 |
| C +200 ms, `B_t = [3]` | 5,813 | 5,467 | 3,215 | 4,832 |

B and C should be indistinguishable. They are not: C sits **16.8%** below B.
But C's three values span 3,215 to 5,813 — a coefficient of variation of
**28.7%** against B's **1.1%** — and C's third repetition reports a mean latency
of 36.06 s. **This run does not establish that the guard is free when no
election occurs; it establishes that at this operating point the instrument
cannot tell.** An earlier internal note read it as showing zero cost without
elections. It does not, and that reading is withdrawn.

### `evidence/05_arms_rerun_aborted/` — aborted, no data

`arms.csv` has empty `success` and `failed` fields and a block count of
`-61591`, because `height_end` was never written. The run was killed partway;
its forty elections are in `elections.csv` and nothing else here is usable.

### `evidence/06_campaign/` — the real attempt

Two seeds, arm order alternated, 100 forced elections per arm, +200 ms on
orderer3 with `limit 10000`, bounded-state `updateAsset.js` over a fixed key
pool, load generator on an instance of its own, and clean brackets before,
between and after each seed. The rig's clean baseline holds to **0.069%** over an
hour and 44 consecutive measurements (`11_potency/xhost_remeasure_2026-09-14/
calibration_1h.csv`).

Every arm submits the same 885,008 transactions:

| arm | committed | failed | fail rate | duration | committed/s | target led |
|---|---|---|---|---|---|---|
| s1 vanilla | 325,204 | 559,804 | 63.3% | 3,257 s | 99.8 | 9/100 |
| s1 guarded | 306,652 | 578,356 | 65.4% | 3,519 s | 87.1 | 0/100 |
| s2 guarded | 337,268 | 547,740 | 61.9% | 3,902 s | 86.4 | 0/100 |
| s2 vanilla | 359,801 | 525,207 | 59.3% | 4,266 s | 84.3 | 9/100 |

The clean brackets around these arms committed 18,008 of 18,008 at the same
offered rate, except `s1_mid` (17,839 committed, 169 failed). The 59–65% is set
by the forced-election duty cycle, not by the delayed follower (see the correction
at the top).

**The result depends on which normalisation is used, and the two disagree.**
On total commits out of a fixed 885,008 submitted, the guarded arm is **5.70%**
and **6.26%** below vanilla. But the arms did not run for equal time — duration
is an outcome here, set by how long 100 forced elections take — and per second of
load the same data gives **−12.73%** for seed 1 and **+2.48%** for seed 2. The
two seeds do not agree in sign. Neither reading is reportable; both are stated
because picking one after seeing the numbers would not be.

### Why the effect was never going to be visible

Recovering the per-block record from the peer logs — **244,868 commits** and
**402 leader terms** — settles what the design got wrong:

| hypothesis | test | result |
|---|---|---|
| o3's terms ended early under the guard | term duration | **no** — median 35.5 s, same as every other node's 36–37 s |
| the guard slowed election recovery | pause → new leader | **no** — 6.22 / 6.49 / 6.52 / 6.63 s across the four arms |

What was wrong is the premise. The 65% figure is measured with o3 pinned as
leader for a whole 60 s window and no elections running. Where an election turns
every ~35 s, the realised penalty is:

| arm | o3 leading | healthy leader | o3's penalty |
|---|---|---|---|
| s1 vanilla | 94.4 tx/s | 114–133 | **−23%** |
| s2 vanilla | 122.5 tx/s | 139–155 | **−16%** |

and o3 holds leadership for only **8.1%** and **6.4%** of the load window. The
effect actually available to be measured was therefore about **1.4%**, not the
~6.8% the design was powered for. **Multiplying two quantities measured in
different regimes was the design error, and it was ours — the paper does not
multiply them.**

### What is left unexplained

The deficit does not come from o3. Comparing only the windows in which a
*healthy* orderer led — o3 a follower in both arms, the guard with nothing to do:

| seed | vanilla | guarded | difference |
|---|---|---|---|
| 1 | 124.8 tx/s | 117.6 tx/s | −5.8% |
| 2 | 144.4 tx/s | 131.6 tx/s | −8.9% |

Why a standing `B_t = [3]` would slow a healthy leader while elections are
turning is not recoverable from these logs, and it would need instrumentation
inside the orderer. It is not raised as a challenge to the paper, and the
reasons are stated rather than assumed: the isolation run that would test it
cannot resolve anything at this operating point (above), the four arms are 40%
unbalanced in how many elections fell inside their load windows (89/81/72/64),
there are two seeds, and every arm is dropping 60% of its offered load. An
unexplained number from an experiment with a known design fault is a record to
keep, not a finding.

## Files

```
README.md                              this file
scripts/expB_pilot.sh                  single-host pilot (runs 01, 02)
scripts/expB_xhost_pilot.sh            cross-host pilot (run 03)
scripts/expB_isolate.sh                isolation control (run 04)
scripts/expB_arms.sh                   arms re-run after the queue fix (run 05)
scripts/expB_campaign.sh               the campaign (run 06)
evidence/01..06/                       one directory per run, in order
evidence/06_campaign/commits.csv.gz    per-block commit record, 244,868 rows
evidence/06_campaign/leaders.csv       402 leader terms
evidence/06_campaign/line_s*_{pre,mid,post}.txt   clean brackets
```

The bring-up and load-generation scripts these call are in the parent directory
(`xhost_setup_all.sh`, `xhost_caliper.sh`, `xhost_caliper_net.sh`,
`local_setup.sh`, `xhost_cc_or.sh`), and the workload is
`11_potency/xhost_remeasure_2026-09-14/updateAsset.js`.
