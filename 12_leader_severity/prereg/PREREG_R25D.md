# Pre-registration — R25D: how often does a degraded leader *stall* the channel?

**Written before the first run of this extension, and after R25C closed at its
registered stopping point.** R25C is complete and is not reopened by this
document: its primary endpoint stands as reported.

- Harness: `alg1/r25_leader_cost3.sh`, **unchanged** (sha256 `c997d7b0…9a30`)
- Parameters: `200 40`, `SKIP_SETUP=1`, unchanged
- Cluster: the same 7-consenter `mychannel`, unchanged
- Output prefix: `results/r25c_<timestamp>/` (unchanged, so the two campaigns
  pool cleanly)

---

## 1. Why this extension exists, and why it is not a re-run of R25C

R25C answered its question and stopped where it said it would. At twelve valid
runs the primary endpoint was

    median R = 0.3553, 95% bootstrap CI [0.2838, 0.3563], half-width 0.0362

and the registered rule was to extend only if the half-width exceeded 0.05. It
did not, so R25C stopped at twelve. **This extension does not touch R.** Adding
runs to sharpen an endpoint that already met its precision target would be
exactly the "extended after seeing the result" pattern the manuscript has had to
disclose once already, and it is not what is being done here.

What R25C found instead was a structure nobody had registered a question about:
the loss is **bimodal**. In ten runs the channel degraded but kept committing,
failing about 14% of submissions; in two it effectively stalled, failing about
96%. The two modes are cleanly separated — no run fell between 15% and 95% —
and they behave differently afterwards, the stalling runs recovering to baseline
at once while the degrading runs leave a backlog for minutes.

That raises a question R25C cannot answer: **how often does the stall happen?**

    observed 2/12 = 16.7%,  95% Wilson CI [4.7%, 44.8%]

An interval that wide supports no statement at all. Estimating a proportion
needs far more samples than estimating a ratio of medians, which is why twelve
runs settled one question and left the other open.

## 2. The question

**Primary endpoint of R25D:** the proportion of valid runs whose `L_leader` arm
*stalls*, with a 95% Wilson interval.

**Stall is defined before the data is extended,** as: the failure fraction of
the `L_leader` arm at offered 500 tx/s exceeds **0.50**.

The threshold is set at 0.50 because the twelve R25C runs fall in two clusters,
13.8–14.7% and 95.7–95.9%, with nothing in between; any cut-off between 0.2 and
0.9 classifies the existing data identically. The threshold is therefore not a
tuning knob, and it is fixed here so that it cannot become one.

## 3. Sample size

**36 valid runs, fixed. No conditional extension, no interim look.**

At an expected 1-in-6 rate this gives roughly 6/36 and a 95% Wilson interval of
about [7.9%, 31.9%], a half-width near 12 percentage points. That is enough to
support a statement of the form "roughly one run in six" and not enough to
support a sharper one; the manuscript will claim no more than the interval
allows. Larger samples were considered and rejected as poor value: 110 runs
would buy a half-width of 6.9 points for 53 hours of cluster time.

There is no stopping rule to game because there is no stopping rule: the
campaign runs to 36 valid and stops, whatever the proportion looks like on the
way.

## 4. Pooling with R25C

The twelve R25C runs **are pooled** into the 36. This is legitimate here and the
grounds are stated so they can be checked: the harness is byte-identical (same
sha256), the delay and pin budget are the same arguments, the cluster is the
same channel with the same seven consenters, and the definition of a valid run
is unchanged. Nothing about the procedure differs between the campaigns; only
the question being asked of the output does.

So 24 further valid runs are required, about 11.6 hours at the observed 29
minutes per run.

## 5. Analysis

- Report **all 36 runs**, individually, with their failure fractions. No run is
  dropped for its outcome, and the two stalling runs already observed are
  reported like any other.
- Primary: stall proportion with a 95% Wilson interval.
- Secondary, reported for consistency and **not** as a new decision: median R
  over the full 36 with its bootstrap CI. If it moves materially from 0.3553 the
  fact is reported; the R25C conclusion is not retro-fitted to it.
- Secondary: whether the two modes remain cleanly separated, i.e. whether any
  run lands between 15% and 95% failure. A filled gap would mean the bimodal
  description is wrong and must be replaced by a continuum.
- Secondary: the aftermath asymmetry (stalling runs recovering at once,
  degrading runs holding a backlog), tested on the larger sample.

## 6. Validity rules

Unchanged from PREREG_R25C section 6. A run is invalid, and replaced, if
`verify_clean` aborts, if any arm commits nothing, or if pinning fails. Invalid
attempts are counted and reported with their reasons.

## 7. What would change the conclusion

- **If the gap fills** — runs appearing between 15% and 95% failure — the
  "bimodal" claim is withdrawn and the result is described as a continuous
  spread, with the median and range reported instead of two modes.
- **If the stall proportion's lower bound reaches 0** at 36 runs, that is, if
  0/36 stall, the two R25C observations are reported as a rare event whose
  frequency this work does not establish, and no rate is claimed.
- **If median R over 36 leaves the R25C interval** [0.2838, 0.3563], both values
  are reported side by side and the discrepancy is discussed rather than
  averaged away.

## 8. What this extension is not

It is not an attempt to improve, stabilise or re-decide R. It is not licence to
drop the two stalling runs: they are valid measurements produced by an unchanged
procedure, and section 5 requires them to be reported. Their existence
strengthens rather than weakens the manuscript's claim, since they show the
failure mode the guard is there to prevent.
