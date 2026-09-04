# Which script drew which figure

Figure 7 (the white-box adaptive adversary) has been drawn four different ways
over the life of this paper, and three of those scripts are still here. A reader
comparing them without a map would reasonably conclude the numbers are unstable.
They are not: two of the four plot a value the paper retracts, and one is a
superseded pass at the correction.

| script | what it draws | status |
|---|---|---|
| `revision/mk_fig_whitebox.py` | **Fig. 7 as it appears in the paper** | **current** |
| `submission/실험그림 재생성/recreate_fig_pgd_corrected.py` | an earlier corrected pass, output `fig_pgd_corrected.pdf` | superseded |
| `submission/실험그림 재생성/recreate_fig_pgd.py` | the retracted AUC floor of 0.73 | retracted, kept for provenance |
| `../01_testbed_harness/alg1/mk_lp.py` | drew the same retracted figure; that half is removed | retracted half removed |

## What was retracted, and why

The submitted Figure 7 plotted an AUC series of 0.774 / 0.748 / 0.733 / 0.819
across autocorrelation floors, and read a worst case of 0.73 off it. That floor
came from a single restart initialised at autocorrelation 0.85, so the search
never entered the low-correlation region it existed to explore. Under a
projected search -- every iterate pushed back inside the threat model, marginals
held exactly at 8.00/3.00 -- the same detector reaches AUC 0.003.

Reviewer 3 counted the 0.73 as a strength of the submitted paper. Section V-E
withdraws it, and the current figure draws the withdrawn floor as a labelled
reference line so the comparison is visible rather than asserted.

## The one to run

    python 10_figures/revision/mk_fig_whitebox.py

It reads `08_predictor/r12_panel/panel2_results.json` directly -- 8 families x
144 runs -- so the plotted worst cases cannot drift from the numbers the paper
reports. The two retracted scripts hardcode their values and must not be re-run
to produce a figure.
