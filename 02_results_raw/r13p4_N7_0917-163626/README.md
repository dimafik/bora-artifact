# Eviction policies with the degraded orderer leading, six seeds (R1-2), N = 7

This supersedes `../r13p3_N7_0917-122908/` for the paper. Same question, two
things fixed:

* **Six seeds, 36 cells** instead of two seeds and 12. `r13p3`'s own README
  said its 20% reversal was one seed against one and not established.
* **A demotion is a demotion, not a pause.** `r13p3` emulated one by pausing the
  incumbent for 9 s, because the v4 binary exposes no way to drop a sitting
  leader. The v5 binary makes the Active-Leader Rule a property of the binary:
  `/tmp/bora-alr-off` lets the tick guard apply to the incumbent as well, so
  arm `D` and arm `P` demote through the guard itself
  (`../../01_testbed_harness/alg1/r13_p4.sh`, `alr_switch`, `push_policy`).

Two runs make up the 36 cells: `r13p4_N7_0917-163626` covered seeds 1-4 in full
and stopped inside seed 5 when the injector gate fired; `r13p4_N7_0917-223327`
resumed at seed 5. Nothing is counted twice.
`../../01_testbed_harness/alg1/agg_p4.py` joins them and prints every cell.

    r13_p4.sh 7 6 300 '10 20'     # N, seeds, dwell seconds, false-positive rates

| arm | what sits above the advisor |
|---|---|
| `A` | the Active-Leader Rule as shipped -- the incumbent is exempt |
| `D` | demote whenever the advice names the leader |
| `P` | demote only after the advice has named the leader for 10 s, and at most once per 60 s |

## Result (36 cells, six seeds)

| arm | correct demotions | wrong demotions | degraded node's tenure | leaderless time | safety violations |
|---|---|---|---|---|---|
| A | 0 of 12 | 0 | **219.2 s** | 0.0 s | 0 |
| D | **12 of 12** | 21 | 5.0 s | 0.5 s | 0 |
| P | **12 of 12** | 14 | 5.3 s | 0.2 s | 0 |

Both eviction arms removed the degraded leader in every one of the twelve cells
they ran. Under the rule as shipped the degraded orderer held the chair for the
whole window in all twelve, which is the cost the rule buys.

**Two numbers changed from `r13p3`, and one of them matters.**

* *Leaderless time, 5.5-7.0 s -> 0.2-0.5 s.* `r13p3`'s figure was the 9 s pause,
  not the demotion. Measured through the guard the availability cost of acting
  on advice is roughly an order of magnitude smaller.
* *"The guarded policy halves the wrong demotions" does not survive six seeds.*
  14 against 21 is about a third, and paired by (rate, seed) the hold-and-
  cooldown policy is better in 6 cells, worse in 4 and tied in 2 -- a one-sided
  sign test gives **p = 0.38**. The reduction is reported, not established.

## What to be careful about

* **Seating is uneven.** `seat_attempts` runs from 0 to 25: the degraded orderer
  is the hardest node to seat, for the same reason it wins elections below its
  chance share. Cells are not equally disturbed before the measurement starts.
* **`A` is not a no-op arm.** It runs the same advisor, pusher and injector;
  only the incumbent exemption differs.
* **Safety here means no orderer panicked or logged a fatal error**, which the
  harness checks. It is runtime stability, not consensus safety; that rests on
  Theorem 1.
* `settle_s = 60` is new in this campaign and is recorded per cell.

## Where this lands

The Section V "Operational questions" paragraph of the manuscript
(ver21 onward) and the R1-2 answer in the response letter. `r13p3` is kept
for the record and is no longer cited.
