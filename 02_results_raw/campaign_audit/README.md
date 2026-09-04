# Where the suppression happens: campaign events per arm

Outcome counts alone cannot separate "BORA suppressed the degraded node" from
"the degraded node happened not to win". Both look like a target that never
takes leadership. The discriminating evidence is whether a blacklisted node
still *attempts* to campaign, because Algorithm 2's tick guard is supposed to
stop it at the source rather than let the vote-grant predicate catch it later.

`01_testbed_harness/alg1/x1_campaign_audit.py` counts distinct campaign events
per orderer -- one event is a burst of `MsgPreVote` lines sharing a timestamp --
and buckets them into the election windows recorded in each run's
`elections.csv`.

## Result

Target campaign events falling inside an election window, over the same six
runs as the published campaign (40 elections per arm per run, 240 per arm):

| run | `A_vanilla` | `B_oracle` | `C_predictor` |
|---|---|---|---|
| `x1_N7_20260810-112256`  | 6 | **0** | **0** |
| `x1_N9_20260810-123729`  | 12 | **0** | **0** |
| `x1_N11_20260809-225113` | 7 | **0** | **0** |
| `x1_N15_20260810-130901` | 9 | **0** | **0** |
| `x1_N21_20260810-134353` | 2 | **0** | **0** |
| `x1_N21_20260810-144117` | 6 | **0** | **0** |
| **total** | **42** | **0** | **0** |

The target emitted **44** campaign events in all. 42 fall inside an election
window and every one of those is in the unguarded arm; the remaining 2 fall
between elections, where no arm is active.

So the tick guard stopped every attempt at the source and the vote-grant
predicate was a backstop it never had to use. The simultaneous fail-open of
both guards that Proposition 2 bounds at O(q^3) was never observed.

## Per-election windows, not per-arm

An earlier version of the script took each arm's first-to-last span as a single
window:

    win[arm] = (float(r[0]["t_start"]), float(r[-1]["t_start"]) + 13.0, len(r))

That is wrong here, because `x1_closedloop.sh` interleaves the arms: for each
seed it runs A, then B, then C. An arm's span therefore covers the other two
almost entirely. Measured on `x1_N7_20260810-112256`:

    A_vanilla    02:24:52 - 02:48:09   span 23 min   occupancy 40 x 13 s = 8.7 min
    B_oracle     02:27:11 - 02:50:30   91% overlap with A
    C_predictor  02:29:30 - 02:52:52   81% overlap with A

Under those windows one campaign event is counted in two or three arms at once,
which reported a 33-50% reduction where the per-election count shows complete
suppression. The script now buckets per election, and its header prints the
actual election occupancy next to the span so that a window swallowing its
neighbours is visible rather than silent.

## Why this transcript is here rather than a re-run

The counts cannot be re-derived from what ships in this repository.
`x1_campaign_audit.py` reads `docker logs` from the live orderer containers,
and those containers are recreated at every N bring-up -- the ones running on
the testbed now belong to the most recent bring-up, not to the runs in the
table. The election windows ship (`elections.csv` in each run directory) and
the script ships; the raft container logs are ephemeral and do not. This file
is the recorded output.
