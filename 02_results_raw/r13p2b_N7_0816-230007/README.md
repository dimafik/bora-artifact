# Re-acquisition by a degraded incumbent (R1-2), N = 7

This run and `../r13p2c_N7_0817-000850` are the measurement behind the sentence in
Section V, *Operational questions*: BORA does not evict a sitting leader, so what
it has to bound is whether a degraded leader gets the **next** term.

Harness: `../../01_testbed_harness/alg1/r13_p2b.sh` (p2c is the same script with
seeds 4–8). `orderer3` carries a `netem delay 200ms` for the whole run, verified
before and after. The injector runs at `--rate 0`, so no false positives are
injected and the advised blacklist is the true set, `[3]`.

Per cell: seat `orderer3` as leader, start the arm's pusher, then force five term
ends. A forced term end is `docker pause` of **whoever is leading**, a poll of at
most 25 s for a different leader, then unpause.

| arm | what it pushes | what it is |
|---|---|---|
| `A` | `[]` every 0.5 s | vanilla: the same patched build and the same pusher, with the guard inert |
| `C` | the injector's `[3]` | BORA as deployed |
| `D` | `[3]`, plus a loop that pauses the leader whenever the advice names it | BORA **without** the Active-Leader Rule |

Seeds: A and C have eight (three here, five in p2c); D has three, here only.

## What the paper and the response letter take from this

The A and C arms: the degraded orderer regained leadership **5 of 40** times
under vanilla Raft and **0 of 40** under BORA; one-sided Fisher p = 0.027 over
elections and p = 0.013 over the eight seeds, five of which it regained under
vanilla. A forced term end pauses the sitting leader, so the target could not win
an election that began with it leading: 13 of the 40 under vanilla, where it kept
regaining the term, and 8 of the 40 under BORA. Five of the remaining 27 is its
chance share of a six-candidate field, which is why no p-value is quoted against
the chance share alone.

Column 7 of each `elections.csv` is the advice read from a running non-leader
orderer at the start of that election. All 40 C-arm elections carry `[3]`, so the
zero is enforcement and not a dead code path.

## The two rows in arm D, which are not used anywhere

`cells.csv` records `target_reacquired=1` for `D_s2` and `D_s3`, and in both
`elections.csv` it is election 1 with the blacklist present. We cannot settle what
those rows are from what was preserved:

* the 2 s sampler (`leader_samples.csv`) shows `orderer3` leading only during the
  seating tenure in those cells — `target_tenure_s` is 6 s, against 18 s in the
  A-arm cells where a re-acquisition really happened;
* `demote.log`, which the no-ALR loop writes, holds only the seating demotion, so
  the loop did not see `orderer3` leading either.

So either the guard was bypassed for less than one sample at that election, or
`leader_now` returned a stale read from a node still reporting the paused term.
Arm D is reported nowhere in the paper or the letter, and the ablation that the
paper does report is the separate `r13v3` run.

## What is not here

`run.log`, `fp.log` and `demote.log` stay on the testbed; the per-cell
`elections.csv`, `leader_samples.csv` and the run-level `cells.csv` are what ship.
The panic and fatal-error check ran against the live container logs, which are not
preserved either — `safety_viol=0` and `liveness_fail=0` in `cells.csv` are the
recorded result of that check, not something a reader can re-derive here.
