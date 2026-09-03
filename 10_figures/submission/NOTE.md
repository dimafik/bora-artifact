# Note on the attention-architecture drawings

**None of the `draw_bora_attention_*.py` scripts in this directory produces
Figure 2 of the paper.** They output `bora_attention_arch_v*.png` (~480 KB each);
the paper's process-view figure is a separately authored raster. They are kept
because they were part of how the figure was arrived at, not because a number
depends on them.

## They describe an output head the model does not have

Six of them (`draw_bora_attention.py`, `_v6_full`, `_v7`, `_v8`, `_v9`, `_v9_1`)
state in their headers, and draw in their output panels, something like:

    Output : {benign, risk} logits -> temperature softmax ->
             risk p_t, confidence c_t -> bounded blacklist B_t

**That is not what `08_predictor/predictor/model.py` implements.** Verified
2026-09-02:

* There is no two-logit head and no softmax over classes. `ScorePredictor` has
  three sigmoid heads — `score` (3 horizons x 3 quantiles), `anomaly`, `degrade`.
* There is no temperature scaling anywhere in the model.
* The reference capacity point's own parameter count settles it. A 2-layer,
  `d_model=32`, `FFN=64`, 5-channel encoder with a `Linear(32,1)` head is
  **17,313** parameters, which is the number the paper reports. A `Linear(32,2)`
  head would make it **17,346**. The deployed 4-layer, `d_model=64`, 8-channel
  instance is **141,067**, confirmed against `torch`.
* The deployed advisor (`01_testbed_harness/alg1/predictor_daemon_n.py`) reads
  one number per orderer — `m(X)["score"][0,0,1]`, the 30 s-horizon median
  quantile — and treats a value **below** `0.65` as risky. The sign is the
  opposite of a risk score: lower means worse.
* Confidence does exist, but as the width of the predicted 10-90% quantile band
  (`infer_advice`: `band = hi - lo`, `sleep_ok` when `band < 0.1`), not as a
  softmax margin. The deployed daemon does not use it: it performs substeps
  (b) and (c) of Algorithm 1 and leaves substep (a) inactive.

The paper's Definition 2 and Section III-D have been corrected to the head that
exists, and the paper's Figure 2 has had its `Temperature` pipeline stage
relabelled. These scripts are left as they were run, with this note recording
what is wrong in them, rather than edited after the fact.

## How Figure 2 was repaired

Because the figure is a raster with no generator, its two text defects were
fixed in place rather than by re-authoring the diagram. `fix_fig_process_views.py`
is that repair, run on 2026-09-02, with the file it reads and the file it
produced kept beside it:

| File | What it is |
|---|---|
| `fig_process_views_pre_fix.png` | the figure as submitted |
| `fig_process_views.png` | the same figure after the repair |
| `fix_fig_process_views.py` | the repair, rerunnable from this directory |

Both edits are text-only, so the strip geometry, the arrows and the box radii
are untouched.

* The pipeline strip's `Temperature` box is **relabelled**, not deleted, to the
  risk score that Definition 2 and Algorithm 1 actually consume. The fill is
  clipped to the measured salmon interior so the rounded grey border is never
  painted over.
* The advisor panel's line (a) read `High confidence filer`. Line (b) already
  carries a correctly spelled `filter` in the same font, size and colour 77 px
  below, so that word is copied pixel-for-pixel rather than re-rendered.

Re-running the script writes `fig_process_views_FIXED.png` next to these; it
should be identical to `fig_process_views.png`. It reads the pre-fix backup
rather than its own output, so it is idempotent.

