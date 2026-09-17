# Eviction policies with the degraded orderer actually leading (R1-2), N = 7

The ALR ablation (`r13v3`) answers what happens when the Active-Leader Rule is
simply removed: wrong predictions demoted a sitting leader 159 times. Every one
of those was a false positive, because in that campaign the guard kept the
degraded node out of leadership — so the ablation never tested whether an
eviction policy removes the node it is supposed to remove.

This campaign puts the degraded orderer in the chair first. Harness:
`../../01_testbed_harness/alg1/r13_p3.sh`, derived from `r13_p2b.sh` with the
same bring-up, seating, injector and samplers.

    r13_p3.sh 7 2 300 '10 20'     # N, seeds, dwell seconds, false-positive rates

Per cell: seat `orderer3` (carrying a +200 ms netem delay) as leader, start the
advisor and the false-positive injector, then watch for 300 s.

| arm | what sits above the advisor |
|---|---|
| `A` | the Active-Leader Rule as shipped — the incumbent is exempt |
| `D` | demote whenever the advice names the leader |
| `P` | demote only after the advice has named the leader for 10 s, and at most once per 60 s |

## Result (`cells.csv`, two seeds per cell)

| arm | correct demotions | wrong demotions | degraded node's tenure | leaderless time | safety violations |
|---|---|---|---|---|---|
| A | 0 | 0 | **225 s** | 0 s | 0 |
| D | 4 of 4 | **9** | 6 s | 7.0 s | 0 |
| P | 4 of 4 | **4** | 12.5 s | 5.5 s | 0 |

Both eviction arms removed the degraded leader in every cell. The guarded policy
halves the wrong demotions and removes them entirely at the 10% injection rate
(0 and 0 against 5 and 3); at 20% one seed reversed that (4 against 1), because a
longer hold is easier to satisfy when flags are dense. Leaderless time is the
price of eviction either way: 0 s under the rule, 5.5–7.0 s without it.

## What to be careful about

* **Two seeds per condition.** The 20% reversal is one seed against one seed and
  is not established.
* **A demotion is a pause.** This build exposes no `TransferLeadership`, so the
  policy loops pause the leader for 9 s and unpause it. That is the action an
  operator has here, and it is also how the ablation demoted.
* **Seating is uneven.** `seat_attempts` in `cells.csv` runs from 0 to 25: the
  degraded orderer is the hardest node to seat, for the same reason it wins
  elections below its chance share. Cells are not equally disturbed before the
  measurement starts.
* **`A` is not a no-op arm.** It runs the same advisor and pusher; only the
  incumbent exemption differs.
* The replay in `../../08_predictor/r12_panel/h1h3/run_evict2.py` asks the same
  question of the recorded ablation traces and bounds it one-sidedly (159 → 62
  under a 10 s hold, → 30 with a 60 s cooldown). It cannot show correct
  demotions, since there were none to show; this campaign can.
