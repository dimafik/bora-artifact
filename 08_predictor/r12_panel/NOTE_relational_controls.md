# What the `shuffled` column in `d1b_results.json` and `d2b_results.json` tests

Both files carry a `shuffled` figure beside the primary one. It re-scores the
same inputs with the node axis permuted, and it is a real control for some of
the models here and a tautology for others. Which is which follows from the
architecture, not from the result, so it is worth stating rather than leaving a
reader to notice that some rows match to four decimals.

## `d2b_results.json` — attribution AUC across cluster sizes

| model | `auc` vs `shuffled` |
|---|---|
| `mlp-concat` | differs, by up to 0.0090 |
| `conv2d` | differs, by up to 0.0011 |
| `gru-nodes` | differs, by up to 0.0026 |
| `attention` | **identical at every N** |

## `d1b_results.json` — top-1 accuracy

| model | `top1` vs `shuffled` |
|---|---|
| `per-node` | **identical** (0.247) |
| `mean-dev` | **identical** (0.7105) |
| `conv2d` | differs (0.2285 vs 0.2300) |
| `gru-nodes` | differs (0.6425 vs 0.6315) |
| `attention` | **identical** (0.6705) |

## Why

The three rows that match are permutation-invariant by construction, so
shuffling the node axis cannot change their output:

* `per-node` scores each orderer on its own series and never sees the others.
* `mean-dev` compares a node against a symmetric aggregate of the rest.
* `attention` is permutation-equivariant, and the head that reads it pools
  symmetrically, so the composition is invariant.

For those three the column is a **sanity check** — it confirms the
implementation does not accidentally depend on ordering — and not evidence that
the model uses node identity, because there is nothing for the shuffle to
disturb.

For `mlp-concat`, `conv2d` and `gru-nodes` the column **is** a control. Those
models read the node axis positionally, so a permutation is a genuine
perturbation, and the small gaps above are the size of the effect.

## What the paper draws from this

Nothing in the manuscript cites the `shuffled` column. The claim it makes from
these files is the one in Section V-E: per-node scoring sits at chance on the
"which node is slow" question (0.470 synthetic, 0.526 on live windows), the
cross-node mean collapses once a moment-matched adversary removes the
absolute-RTT cue, and only a pairwise comparison holds in both. Those are the
`auc` and `top1` figures, not the shuffled ones.
