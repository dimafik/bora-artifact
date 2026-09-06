# Which panel file the paper reads

Three files in this directory carry the same eight detector families under the
same seven keys — `name`, `params`, `differentiable`, `non_adaptive`,
`worst_case`, `sweep`, `minutes`. Nothing in the names says which one the paper
reports, and two of the three disagree with it. This is the map.

| file | `non_adaptive` | `worst_case` | sweep size | status |
|---|---|---|---|---|
| **`panel2_results.json`** | **matches Table IV** | **matches Fig. 7** | 144 runs per floor | **current** |
| `panel_results.json` | same as current | ours 0.472, GRU 0.0 | no `all_combos` | superseded |
| `panel2_smoke.json` | ours 0.9998 | ours 0.0952 | 4 runs per floor | smoke test |

The trap is `panel_results.json`. Its `non_adaptive` column agrees with Table IV
exactly, so a reader who opens it first has no reason to doubt it — and then its
`worst_case` column contradicts Fig. 7 outright: 0.472 for our model where the
figure plots 0.003, and 0.0 for the GRU where the figure plots 0.002. That file
predates the projected search. Its iterates were never pushed back inside the
threat model, so its worst cases are not comparable to anything the paper
reports, and it has no `all_combos` record to audit. It is kept for provenance
and must not be read as a result.

    python 08_predictor/r12_panel/panel2.py      # regenerates panel2_results.json

## One file, two places in the paper

`panel2_results.json` feeds two different parts of Section V-E through two
different keys.

**`non_adaptive` → Table IV, adaptive-attack panel.** Detection AUC when the
adversary is not adapting to the detector.

| detector | measured | Table IV (2 d.p.) |
|---|---|---|
| `std(dRTT)` statistic | 0.9982 | 1.00 |
| GRU | **1.0000** | 1.00 |
| Transformer (ours) | 0.9996 | 1.00 |

Two things about this panel that the table cannot show at two decimal places.
Every family saturates: the full column runs 0.9982 to 1.0000 across all eight
entries, so the panel does not rank architectures and nothing should be read
into the order. And our model is not the maximum — the GRU is, at 1.0000 against
our 0.9996. Section V-E says so in the text ("we make no claim for attention on
it"); the ranking that matters is the adaptive one below.

The panel exists to answer a narrower question. On the necessity benchmark our
model scores 0.93 and ranks below a 41-parameter logistic, because that
benchmark trains every family from scratch on forty simulated traces and starves
a 141k-parameter model. Retrained at panel scale the same architecture reaches
0.9996, which is what makes the 0.93 a sample-size effect rather than an
architectural one. That is the whole claim.

**`worst_case` and `sweep` → Fig. 7, white-box adaptive adversary.** Worst AUC
over 36 attack configurations (four initialisations x three learning rates x
three seeds) at each autocorrelation floor, 1,152 runs in all. The per-floor
values are under `sweep["rho_0.0"]["worst_auc"]` and so on; the top-level
`worst_case` is the minimum across floors.

| detector | rho=0.0 | rho=0.3 | rho=0.6 | rho=0.8 |
|---|---|---|---|---|
| Transformer (ours) | 0.0027 | 0.0393 | 0.3324 | 0.9433 |
| GRU | 0.0019 | 0.2319 | 0.8066 | 1.0000 |
| MLP 64-32 | 0.0063 | 0.2150 | 0.9637 | 1.0000 |
| 1D-CNN | 0.2277 | 0.9656 | 1.0000 | 1.0000 |

Section V-E reads two comparisons off this table: ours furthest below chance at
every floor above 0 (0.039 against the GRU's 0.232 at rho=0.3), and level with
the GRU at rho=0 (0.003 against 0.002). Both round from the values above.

Here the ordering is real and it runs the other way from the saturated panel:
under white-box adaptation our model collapses further than any other
differentiable family. That is the paper's point, and it is a statement about
how badly a learned detector fails, not how well it detects. Fig. 7 is drawn by
`10_figures/revision/mk_fig_whitebox.py`, which reads this file directly; see
`10_figures/WHICH_GENERATOR.md` for the two retracted scripts that drew earlier
versions of the same figure.
