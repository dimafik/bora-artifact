# Addendum 01 to PREREG_R25D — two findings the registration did not anticipate

The campaign reached its registered stopping point: 36 valid runs, no extension,
no interim look. This note records two things discovered when the data was
analysed, both of which change how the result must be described. Neither changes
a measurement.

---

## 1. The testbed degraded partway through, and the clean arm caught it

Every run carries its own no-delay baseline. Across the campaign that baseline
was not constant:

    runs  1-23   C_clean at 500 tx/s = 468 tx/s  (+/- 1, on 23 consecutive runs)
    runs 24-25                       = 189, 223
    run  26                          = 468
    runs 27-30                       = 204
    run  31                          = 461
    runs 32-36                       = 202-207

Eleven of the thirty-six runs were therefore taken on an instrument delivering
44% of its usual throughput.

**Cause.** The collapse tracks ledger size, not time. Correlating each run's
starting block height against its clean baseline gives a Pearson r of **-0.746**,
with a threshold near 570,000 blocks:

    starting height < 400,000 : mean clean baseline 468.3 tx/s (n=15)
    starting height >= 400,000: mean clean baseline 329.4 tx/s (n=21)

The channel began the campaign at height 3,650 and ended at 905,020, with each
orderer's ledger directory reaching 36 GB. Past roughly 570k blocks this
single-host seven-orderer cluster can no longer sustain 468 tx/s. Two runs above
the threshold still measured 468 and 461, so the effect is a rising probability
of collapse rather than a hard cliff.

**Consequence for the analysis.** The registered primary is reported as
registered, over all 36 runs. A restriction to the 25 runs whose own clean arm
measured at least 450 tx/s is reported alongside it as a sensitivity analysis,
labelled post-hoc. The restriction is an instrument check, measurable without
reference to the outcome, in the same spirit as the existing `verify_clean`; and
it moves the headline **against** the paper, from 36.1% to 32.0%, so it is not a
filter chosen for its answer.

    stall proportion, all 36 runs        13/36 = 36.1%  95% CI [22.5%, 52.4%]
    stall proportion, 25 verified runs    8/25 = 32.0%  95% CI [17.2%, 51.6%]
    median R, all 36                     0.3563
    median R, 25 verified                0.3452

The two agree well inside their intervals. The conclusion does not depend on the
split.

**Not repairable by re-running.** The ledger only grows. Re-running the eleven
affected runs on this cluster would start above 905,000 blocks and reproduce the
collapse; restoring the baseline would require rebuilding the channel, which is
the bring-up path that failed in five of seven attempts in the predecessor
campaign, and would leave the earlier runs measured on a different instrument.

---

## 2. "Bimodal" was the wrong description. It is a recovery-time distribution

The registered analysis looks at 500 tx/s alone, and at that slice the runs do
separate cleanly: failure fractions of 11-15% in one group and 95-100% in the
other, with nothing between. The gap check of section 5 therefore passed.

Reading the whole sweep instead of the last point shows that this separation is
an artefact of where the window ends.

**All twenty-five runs begin identically.** At 100 tx/s every run fails 45-60%
of submissions; at 200 tx/s every run fails 76-89%. The two groups are
indistinguishable there. They diverge at 300 tx/s, where seventeen runs drop to
10-27% failure and eight stay at 88-89%.

**And the divergence point itself varies.** Run `20260825-141245` was still at
65% failure at 300 tx/s and recovered at 400. Run `20260825-134203` was at 88%
and 74% through 300 and 400 tx/s and recovered only at 500. These are
intermediate cases; the "gap" is empty only because the sweep stops at 500.

What the eight so-called stalling runs have in common is not a distinct failure
mode but that they had **not yet escaped the backlog when the sweep ended**.
Their arm also took longer: a median of 719 s against 594 s.

**Alternative explanations ruled out.** Leadership is retained in all
twenty-five runs (`3 -> 3` in every `arms.csv`), so the divergence is not the
leader being deposed. Pinning difficulty does not separate the groups either,
and runs the wrong way: the non-recovering runs needed fewer restarts to pin
(6.6 against 8.4 on average). The failures are not a client-side artefact: block
production matches the reported successes in both groups (2.0 tx/block against
4.6, and 5.0 blocks/s against 12.1), so the ledger did not quietly commit what
Caliper counted as failed.

**Consequence.** Under section 7 of the registration, a filled gap requires the
bimodal description to be withdrawn in favour of a continuous one. The gap is
empty at the registered slice but the mechanism underneath is continuous, and
two runs sit in the middle of it. We therefore describe the result as a spread of
recovery times truncated by the measurement window, and report the 8/25 figure
as "did not recover within the sweep" rather than as a stall rate. The numbers
are unchanged; the claim attached to them is weaker and matches what was
observed.

**A note on why this is the safer claim.** "The channel stops about a third of
the time" invites the question of whether it stops permanently, which this
campaign cannot answer. "Eight of twenty-five runs had not recovered when the
sweep ended after 150 s of load" is the observation itself, and needs no defence.

---

## 3. What stands unchanged

- Every measurement, every run, every raw file.
- The registered primary endpoint and its interval.
- The asymmetry between a delayed leader and a delayed follower, which is the
  result the manuscript actually uses: a median 65.5% loss against 20.7%, a
  factor of 3.2, on the 25 verified-baseline runs.
- The aftermath asymmetry, which the recovery reading explains rather than
  contradicts: runs that fail fast leave no queue and return to baseline at once
  (median D = 1.00), while runs that succeed slowly accumulate a backlog that
  holds the channel near 44% of baseline for minutes after the delay is removed.
