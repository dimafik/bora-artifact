# The detector: training, baselines, and the adaptive-attack panel

Everything the paper says about the learned detector is produced here. Two
things this directory does *not* settle are settled elsewhere: which advisor
binary actually ran in the closed-loop campaign
(`../01_testbed_harness/alg1/WHICH_ADVISOR.md`) and which results file the
paper's Table IV and Fig. 7 read (`r12_panel/WHICH_PANEL.md`). Read those two
first if you are checking a number rather than re-running a script.

## What supports which claim

| Paper | Here |
|---|---|
| Fig. 4 and Section V-B — the detector in the loop | `predictor_daemon.py` (superseded; the trace it produced is the one the paper plots), `predictor_daemon_n.py` (the spec-conformant cap, used for the campaign) |
| Table IV, adaptive-attack panel | `r12_panel/panel2_results.json`, `non_adaptive` column |
| Fig. 7 — white-box PGD, worst case over 1,152 runs | `r12_panel/panel2_results.json`, `worst_case` and `sweep` |
| Section V-E — the moment-matched adversary | `mm_train.py`, `mm_feas.py`, `mm_analyze.py`, `mm_adaptive.py`, `best_mm.pt` |
| R1-1 — does the task need a Transformer? | `lightweight_baselines.py`, `r11_necessity_baselines.py`, `r11_mm_baselines.py`, `r11_pgd_baselines.py`, `r11_pgd_strong.py` and their `.json` outputs |
| Section III-H — Kubernetes deployment | `deploy/` holds a Dockerfile, a compose file, a Helm chart and multi-region manifests. **None was deployed or measured.** Section III-H says the design carries to Kubernetes and that no Kubernetes artefact forms part of this evaluation; these are here so that claim can be read against something rather than taken on trust. |
| Deployed checkpoint provenance | `predictor/` (the training code, kept as it
ran and still using the earlier project's vocabulary in its comments; see `../MANIFEST.md` on its train/val/test split, which is optimistic and which no paper number rests on), `model_full/`, `model_small/`, `model_xl/`, `model_xl2/` |

`feas_test.py` and `feas_test2.py` are the feasibility gate that came before any
of it: can the trained model tell the attacked orderer from live RTT telemetry
at all. `necessity_output/`, `data_small/`, and the `*_results.txt` files are
outputs kept next to the scripts that wrote them.

## Pre-registration

`r12_panel/PREREGISTRATION.md`, `PREREG_R1R2.md` and `PREREG_D1D2.md` fix the
conditions before the results were seen. The adaptive-evaluation protocol the
paper follows makes that ordering the point rather than a formality.

## What used to be here

This directory grew out of an earlier project of ours built on a different
consensus algorithm, and until this revision it still carried that project's
design documents, TLA+ specification, draft manuscript sections and simulation
results. None of it supported a claim in this paper, and its vocabulary
(a learner replacing a ranking function inside the consensus path) describes
the opposite of what BORA does: a bounded advisor that can only remove
candidacy, outside the consensus path. It has been moved out to avoid reading
as a second, contradictory account of the same system. The git history still
holds it if provenance is needed.
