# What the Active-Leader Rule is worth, and which directory holds it

Phase 1 of the r13v3 campaign removes exactly one rule. Three arms run the same
36 cells at N=7: **A** is vanilla Raft, **C** is BORA, and **D** is BORA with
only the Active-Leader Rule taken out, so the predictor may demote a sitting
leader. The cap, both guards and the fail-open counter are identical in C and
D. That is what makes this an ablation of one rule rather than a comparison of
two systems -- and it is an ablation of *our* rule, not a measurement of AWARE
or BFTBrain, neither of which was run.

## Read this directory first

Three directories share the `r13v3_N7_*` prefix and only one is the campaign:

| directory | P1 cells | status |
|---|---|---|
| `r13v3_N7_0815-193211` | 3 | partial bring-up, p=20% only, 4 elections |
| `r13v3_N7_0815-195411` | 6 | partial bring-up, p=0% only, 2 elections |
| **`r13v3_N7_0815-202027`** | **36** | **the campaign** |

Globbing all three and summing gives **168** demotions, not the 159 the paper
reports, because it folds in nine demotions from a four-election fragment. The
campaign alone gives 159. The partials are kept as a record of the bring-up
rather than as data, the same way `partial_N15_run4.log` and the `INVALID_*`
directories are kept elsewhere in this repository.

    python3 02_results_raw/r13v3_alr_ablation/alr_report.py

## Result

360 forced elections, 120 per arm, four injected false-positive rates.

| arm | | elections | demotions | of which true-positive | leader changes | leaderless | safety violations |
|---|---|---|---|---|---|---|---|
| A | vanilla Raft | 120 | 0 | 0 | 439 | 254 s | 0 |
| C | BORA | 120 | **0** | 0 | 557 | 256 s | 0 |
| D | BORA minus ALR | 120 | **159** | **0** | 1,111 | 532 s | 0 |

Demotions by injected false-positive rate:

| arm | p=0% | p=5% | p=10% | p=20% |
|---|---|---|---|---|
| C | 0 | 0 | 0 | 0 |
| D | 0 | 41 | 58 | 60 |

## Three things the table says

**C's zero is not dead code.** Advice carrying a false positive reached an
orderer in 70 of C's elections, and the leader still never moved. Delivery
happened; enforcement refused. The `advice_seen` column is what shows this, and
it is the direct answer to the concern that the guarded arms might simply never
have been exercised.

**Every one of D's 159 demotions was caused by a false positive.** The
true-positive column is 0 across all four rates. Give the predictor authority
and a wrong prediction becomes a protocol event, one for one.

**The cost lands on availability, not safety.** All three arms record zero
safety violations; what changes is leaderless time, which reaches **2.90x**
vanilla Raft for arm D at p=20% (174 s against 60 s). That ratio is against arm
A. Against C it is 2.64x, because C itself sits within a few per cent of
vanilla throughout.

## A word on "forced leader changes"

The paper's 159 is the `demotions` column: leader changes the advisor caused by
demoting an incumbent. The `leader_changes` column is larger (1,111 for D)
because it counts every turnover including the ordinary end of a term. The two
are different quantities and the ablation is about the first.

## Files

| file | what it is |
|---|---|
| `alr_report.py` | recomputes every number above from the campaign's `cells.csv` |
| `../r13v3_N7_0815-202027/cells.csv` | the campaign, 36 Phase-1 cells |
| `../r13v3_N7_0815-202027/P1_*/` | per-cell election logs and leader samplers |
