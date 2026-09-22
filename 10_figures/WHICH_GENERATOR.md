# Which script drew which figure

One row per figure in the paper: what draws it, what it reads, and whether it
runs as shipped. Two things this map exists to prevent — reading a retracted
script as current, and concluding a figure has no provenance when it has none
by design.

| Paper | File | Generator | Reads | Runs as shipped |
|---|---|---|---|---|
| Fig. 1 | `fig_architecture.pdf` | **none — hand-drawn** | — | n/a |
| Fig. 2 | `fig_process_views.pdf` | `submission/fix_fig_process_views.py` | `submission/fig_process_views_pre_fix.png` | yes |
| Fig. 3 | `fig_prism_convergence.pdf` | `../01_testbed_harness/alg1/make_g1_g2.py` (first half) | `../01_testbed_harness/alg1/prism_sweep.txt` | no — absolute path |
| Fig. 4 | `fig_detection_ac.pdf` | `../01_testbed_harness/alg1/mk_fig67_academic.py` (**first half only**) | `../02_results_raw/mldetect_20260611-171955/predictor_daemon.log` | no — absolute path |
| Fig. 5 | `fig_exclusion_stack.pdf` | `../01_testbed_harness/alg1/mk_fig_exclusion_stack.py` | counts inline (7/36, 0/36, 10/40, 3/40, 4/20, 0/20, 2/16, 0/16); raw logs under `../02_results_raw/` | no — absolute path |
| (withdrawn) | `fig_loadsweep.pdf` | `../01_testbed_harness/alg1/mk_lp.py` | E1/E2/E3 sweep values inline | disabled — the figure was withdrawn in the revision: its CLI sweep never waited for commit and reused asset keys across concurrency levels |
| Fig. 6 | `revision/fig_scope_wide.pdf` | `revision/mk_fig_scope_wide.py` | `../02_results_raw/x1_N*/elections.csv`, `../02_results_raw/r13*/**/elections.csv`, `../08_predictor/r12_panel/` | **yes** — prints its own counts (1,440 cells, 45 acquired, 1,555 cited, 0/480 guarded, 21 unguarded, 1,152 PGD) |
| Fig. 7 | `revision/fig_whitebox_clean.pdf` | `revision/mk_fig_whitebox.py` | `../08_predictor/r12_panel/panel2_results.json` | **yes** — the paper ships the *clean* variant, without the 0.73 reference line the marked copy carries |

"Runs as shipped: no" means only that the script names the absolute path it was
run from rather than the copy in this artifact. The data is here, at the path in
the Reads column, and the values match: `prism_sweep.txt` reproduces
`1-(1-q)^k` exactly for q = |E_t|/2^|E_t|, and the daemon log parses to the 158
cycles Section V-B reports. The scripts are kept as they ran rather than
rewritten, which is the same rule the rest of this artifact follows.

## Fig. 1 has no generator, and that is not an omission

It is an architecture diagram, drawn by hand. Nothing in it is measured, so
there is no data file behind it and no script to re-run. It is listed here so
that an audit asking "is every figure reproducible?" gets an answer rather than
a silence.

## Fig. 4 shares a file with a retracted figure

`mk_fig67_academic.py` draws two figures. The first (to line 127) is Fig. 4 and
is live: it reads the daemon log and hardcodes nothing. The second (from line
131) is an old white-box figure that hardcodes the retracted AUC series and must
not be re-run. The file's header used to warn about the second half in a way
that read as a warning about the whole file; it now says which half is which.
`mk_fig67_rich.py` and `mk_pgd_rich.py` carry the same blanket warning and there
it is correct — neither draws a figure that appears in the paper.

## Fig. 7 has been drawn four ways; three of those scripts are still here

A reader comparing them without a map would reasonably conclude the numbers are
unstable. They are not: two of the four plot a value the paper retracts, and one
is a superseded pass at the correction.

| script | what it draws | status |
|---|---|---|
| `revision/mk_fig_whitebox.py` | **Fig. 7 as it appears in the paper** | **current** |
| `submission/실험그림 재생성/recreate_fig_pgd_corrected.py` | an earlier corrected pass, output `fig_pgd_corrected.pdf` | superseded |
| `submission/실험그림 재생성/recreate_fig_pgd.py` | the retracted AUC floor of 0.73 | retracted, kept for provenance |
| `../01_testbed_harness/alg1/mk_lp.py` | drew the same retracted figure; that half is removed | retracted half removed |

### What was retracted, and why

The submitted Figure 7 plotted an AUC series of 0.774 / 0.748 / 0.733 / 0.819
across autocorrelation floors, and read a worst case of 0.73 off it. That floor
came from a single restart initialised at autocorrelation 0.85, so the search
never entered the low-correlation region it existed to explore. Under a
projected search -- every iterate pushed back inside the threat model, marginals
held exactly at 8.00/3.00 -- the same detector reaches AUC 0.003.

Reviewer 3 counted the 0.73 as a strength of the submitted paper. Section V-E
withdraws it, and the current figure draws the withdrawn floor as a labelled
reference line so the comparison is visible rather than asserted.

### The one to run

    python 10_figures/revision/mk_fig_whitebox.py

It reads `08_predictor/r12_panel/panel2_results.json` directly -- 8 families x
144 runs -- so the plotted worst cases cannot drift from the numbers the paper
reports. See `08_predictor/r12_panel/WHICH_PANEL.md` for which column of that
file feeds Fig. 7 and which feeds Table IV. The two retracted scripts hardcode
their values and must not be re-run to produce a figure.

## Fig. 6 and Fig. 7 were renumbered during the revision

The scope figure was added in the revision and took number 6, which moved the
white-box figure to 7. This table listed the white-box figure as Fig. 6 until
2026-09-22 and had no row at all for the scope figure -- the one that carries
the corpus counts, and so the one an audit is most likely to look for. Both are
fixed above. The paper includes `fig_whitebox_clean.pdf`; `fig_whitebox.pdf` is
the marked-copy variant that draws the 0.73 reference line.
