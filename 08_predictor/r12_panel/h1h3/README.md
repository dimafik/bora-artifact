# Does a *learned* advisor earn its place? Ten pre-registered measurements

`../hand_rel_eval.py` showed eleven hand-built parameters beating our attention
model on the "one node or the network" task. This directory is what we did about
that: `PREREGISTRATION.md` (written before the runs, including §7, the record of
what the pilot changed in the task definitions), then ten measurements, every
configuration and every discarded run kept.

**The headline is an ordering, not a winner.** As an adversary shapes the same
injected delay to ride the cluster's own jitter, the advisors fail in sequence:

| beta | threshold / MAD rule | correlation rule | hand bank (33 features) | attention | DeepSets |
|---|---|---|---|---|---|
| 0.00 | 0.505 | 1.000 | 1.000 | 0.999 | 0.998 |
| 0.25 | 0.497 | 0.993 | 1.000 | 0.998 | 0.939 |
| 0.50 | 0.501 | 0.830 | **0.941** | 0.521 | 0.680 |
| 0.60 | 0.489 | 0.646 | 0.695 | 0.492 | 0.559 |
| 0.75 | 0.493 | 0.533 | 0.547 | 0.573 | 0.484 |
| 0.80 | 0.498 | 0.515 | 0.527 | 0.537 | 0.522 |
| 0.90 | 0.496 | 0.530 | 0.616 | 0.676 | 0.644 |
| 1.00 | 0.498 | 0.574 | 0.666 | 0.734 | **0.976** |

Three seeds per cell (`run_adv2.py`, `run_rules_sweep.py`). A threshold on the
level is at chance the moment the level cue is gone; a zero-parameter correlation
rule holds to a quarter of full mimicry; the hand bank to a half; at full mimicry
only a learned model still separates. That ordering is the case for a learned
advisor, and Section V-C states it.

**It is not a case for attention.** Attention led in none of the ten
measurements. A first pass gave it 0.991 and 0.997 at beta 0.9 and 1.0; three
seeds gave 0.676 ± 0.274 and 0.734 ± 0.235. Both are in `results_adv.json` and
`results_adv2.json`, and the second is what we report.

## The ten measurements

| file | what it asks | result |
|---|---|---|
| `run_h.py` → `results.json` | H1 a held-out attack family, H2 two regions, H3 size and node order | hand bank 0.95–1.00; attention 0.49–0.68 |
| `run_h.py --big` → `results_big.json` | the same three with every model's budget tripled | learned models recover (F3 0.13 → 1.00); largest attention lead 0.007 |
| `run_t12.py T1` → `results_T1.json` | a timed cascade across nodes, twelve configurations per family | hand 0.995 ± 0.001, DeepSets 0.946, attention 0.867 |
| `run_t12.py T2` → `results_T2.json` | a sparse reference group at N = 21 | hand 0.622, everything learned at chance |
| `run_real.py` → `results_real.json` | attribution on the real daemon log, split by segment | RAW all 1.000; NORM hand 0.17 against learned 0.50 |
| `run_transfer.py` → `results_transfer.json` | train at N = 7, score at N = 9, no refit | RAW all 1.000; NORM hand 0.425 against learned 0.90–0.91 |
| `run_swap.py` → `results_swap.json` | three advisors on the real five-host feeds | Transformer 3.3–4.6 s, cheap rules 2.8–2.9 s, zero false positives for all |
| `run_worst.py` → `results_worst.json` | replay the contract with the worst advice it permits | an eligible majority survives in 1,539 of 1,539 logged elections |
| `run_cost.py` → `results_cost.json` | what each advisor costs on the path the orderer waits on | deployed predictor 1.96 ms of a 50 ms budget; rule 0.03 ms |
| `run_adv.py`, `run_adv2.py`, `run_rules_sweep.py` | the mimicry sweep above | the ordering |

`run_multi.py` is the eleventh question — one model answering detection,
attribution and 30/60/90 s horizons against three separate rules — and it is
**unanswerable on this log**: of 618,322 N = 7 ticks, 549,957 have exactly one
orderer degraded, and the other classes occupy two or three stretches, so no
split leaves both classes on both sides. It is kept for the record.

## How to read the numbers

* Synthetic tasks are ours, so "unknown attack" means unknown among five families
  we wrote; the real-log rows are the ones no one designed.
* The per-node control is at or below chance in every relational task, which is
  what makes them relational; in two families it sits at 0.5–0.6 rather than 0.5
  exactly, because a positive window contains ordinary-looking nodes and a
  negative one does not (`PREREGISTRATION.md` §7).
* Every model got the same stem, depth, schedule, augmentation and search budget;
  the hand bank got the same twelve trials over feature subsets and three
  classifier families (`hand_v2.py`).
* `SUMMARY_ALL.txt` regenerates every table here from the result files.
