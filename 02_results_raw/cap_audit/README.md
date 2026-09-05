# The Algorithm 1 cap, checked on every advice cycle

Algorithm 1 substep (c) emits

    B_t <- top(p_t, H_t, max(f - r - 1, 0))

where `r` is the Raft-observed unhealthy count. Two things follow. The emitted
blacklist obeys `|B_t| <= max(f - r - 1, 0)`, which implies the `|B_t| < f`
that `BORA.tla`'s `BoundedCap` and the safety proof use. And the budget
contracts as the cluster degrades, reaching zero *before* `r` reaches `f`: the
advisor stands down rather than compounding a real failure.

That is a per-cycle contract, so it deserves a per-cycle check rather than a
summary. The advisor writes `r` and the applied cap on every cycle for exactly
this reason.

## Result

    python3 02_results_raw/cap_audit/cap_audit.py

| N | advice cycles | highest `r` observed | cycles with `r >= f` |
|---|---|---|---|
| 7 | 4,887 | 0 | 0 |
| 9 | 3,640 | 0 | 0 |
| 11 | 3,754 | 0 | 0 |
| 15 | 29,118 | 15 | 15 |
| 21 | 9,041 | 0 | 0 |
| **total** | **50,440** | | **15** |

| check | violations |
|---|---|
| `cap != max(0, f - r - 1)` | **0** |
| `\|B_t\| > cap` | **0** |

## The clamp is not decorative

Fifteen cycles at N=15 recorded `r = 15` with `f = 7`. The cluster read as
entirely unresponsive there, which is what a bring-up gap looks like from the
advisor's side. In those cycles `f - r - 1` is `-9`, so it is the `max(., 0)`
that keeps substep (c) defined and the advisor emitting the empty set. Without
it the expression is undefined and the postcondition `|B_t| < f - r` is
unsatisfiable, since no set has negative cardinality.

The contraction itself is visible in the paper's own N=11 audit, where raising
`r` from 0 to 4 walks the cap down 4 → 3 → 2 → 1 → 0, exactly `4 - r`.

## Scope

The log this reads is the B-20 sweep's advisor, which carries the
zero-parameter mean-RTT detector in the scoring slot. Everything downstream of
scoring -- the `r` derivation, the cap, the advice payload, the log format --
is copied unchanged from `predictor_daemon_n.py`, so the cap path under test is
the shipped one and a difference here would be a difference in the envelope,
not in the detector.

The older `mldetect_*` daemon logs predate the per-cycle `r`/`cap` audit trail:
they record `Bt=` and the per-orderer scores but no cap field, so they cannot be
checked this way. What those runs establish is detection latency and false-positive
rate, not the cap.

## Files

| file | what it is |
|---|---|
| `cap_audit.py` | the checker; reads the log below and exits non-zero on any violation |
| `../b20_sweep_20260903-162221/predictor_daemon_meanrtt.log.gz` | the input, 53,031 lines |
