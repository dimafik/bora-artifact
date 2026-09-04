# The closed-loop sweep again, with a zero-parameter detector

The paper's headline exclusion result is 0/240 forced elections under a
detector-produced blacklist. This sweep asks whether that number belongs to the
141k-parameter Transformer or to the envelope around it: the cap
`|B_t| < f - r`, the fail-open counter and the two election guards.

Same harness, same six runs (N = 7, 9, 11, 15, 21, 21 -- four seeds of ten
elections each), same three arms. One thing differs: the function that turns a
telemetry window into a per-orderer score. Everything downstream of that
function -- the feed reader, the `r` derivation, the Algorithm 1 cap, the advice
payload, the log format -- is copied from `predictor_daemon_n.py` unchanged, so
a difference in the outcome is a difference in the detector and not in the
envelope.

## Result

| arm | target wins | 95% Wilson | liveness |
|---|---|---|---|
| `A_vanilla` (unguarded) | **24/240** | [0, 14.4%] | 240/240 |
| `B_oracle` (operator-supplied) | 0/240 | [0, 1.6%] | 240/240 |
| `C_predictor` (**zero-parameter**) | **0/240** | [0, 1.6%] | 240/240 |

One-sided Fisher exact, guarded against unguarded: **p = 3.3e-08**.

The published campaign, with the Transformer in the same slot, reads
A 21/240, B 0/240, C 0/240. The unguarded baseline is alive in both -- the
target does take leadership when nothing stops it -- and the two advisors are
not distinguishable.

Reproduce with `python 01_testbed_harness/alg1/b20_report.py`.

## Which detector, and why not the one the panel names

The detector panel's zero-parameter entry is `std(dRTT)`. That is the right
statistic for the *moment-matched synthetic* task, where the means are equal by
construction and only the variance channels carry signal. It is the wrong one
here. The injected fault on this testbed is a steady +200 ms egress delay: it
moves the mean from about 0.5 ms to about 200 ms and, being steady, *lowers*
dRTT variance rather than raising it. Feeding `std(dRTT)` to the live feed
would measure jitter, not the fault.

The live zero-parameter detector is a mean-RTT threshold, and that is what
`predictor_daemon_meanrtt_wsl.py` implements. It has one calibrated constant,
50 ms, two orders of magnitude from both the healthy and the degraded end.

## What this does not show

The injected fault is an easy one. A threshold that missed a 400x jump in RTT
would be broken, so the run says nothing about detector quality. And it
concerns a different adversary from the moment-matched case, where the paper's
linear-detector ceiling still holds every linear functional at chance. What the
run establishes is the bound, not the detector.

## Files

| file | what it is |
|---|---|
| `x1_N{7,9,11,15,21}_run{1..6}.log` | the six harness runs, one per bring-up |
| `driver.log` | the driver's own trace, including the restart at 21:41 |
| `partial_N15_run4.log` | an aborted first N=15 attempt, kept and excluded |
| `predictor_daemon_meanrtt.log.gz` | the advisor's per-cycle audit trail, 53,031 lines |

`partial_N15_run4.log` is out of the aggregator's glob on purpose. Its first
three seeds completed and its fourth did not, because the driver was a child of
the shell that launched it and went away with it. Mixing three seeds from one
cluster bring-up with one from another is not the same experiment, so N=15 was
run again from scratch and the partial is kept as a record rather than as data.

## Detector precision

Restricted to the attack windows -- the intervals between each run's
`ATTACK_ONSET` and the end of that run -- the advisor's emissions over 21,667
cycles are 99.6% exactly the injected target set, with **no false positive at
any N** and 0.4% of cycles missing the target, which is the detection latency
at attack onset. Outside those windows the correct emission is the empty set,
and counting those cycles as misses is what made an earlier reading of this log
report a precision loss that is not there.
