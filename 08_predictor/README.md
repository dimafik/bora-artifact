# Pivot v26: Score-Predictor for S-Raft

**Decision date**: 2026-06-01
**Replaces**: BRAO oracle for Fabric tx ordering (v25)
**New thesis**: Learn the S-Raft sub-leader Score function with a 0.56 MB
Transformer; reuse the backbone for prediction, security, and maintenance.

## Layout

```
pivot_v26/
├── PREDICTOR_SPEC.md          # formal predictor specification
├── AUGMENTATION_THEOREM.md    # safety proof
├── predictor/
│   ├── model.py               # ScorePredictor (141K params)
│   ├── data_synth.py          # synthetic S-Raft trace generator
│   └── train.py               # multi-head training loop
├── paper/
│   └── paper_section_v26.tex  # drop-in LaTeX for v26 manuscript
├── data_small/                # 20-trace dev dataset (validated)
└── model_small/               # 5-epoch dev checkpoint (validated)
```

## Validation status (dev run)

| Component | Result | Status |
|---|---|:---:|
| `model.py` sanity | 141,067 params, all heads produce correct shapes | ✓ |
| `data_synth.py` | 20 traces × 4 scenarios = 7,200 windows | ✓ |
| `train.py` 5-epoch | Anomaly AUC 0.994, Score RMSE@30s 0.136 (small data) | ✓ |
| Pre-reg Anomaly threshold (≥0.90) | 0.994 | ✓ |
| Pre-reg Score RMSE (≤0.04) | Pending full-scale data | wait |
| Pre-reg Degrade AUC (≥0.70) | NaN (n_ticks too short for 1h labels in dev) | wait |

## To reach paper-ready full training

1. **Generate full dataset** (≈30 min CPU):
   ```bash
   python predictor/data_synth.py --out-dir data_full \
     --n-traces 80 --n-nodes 5 --n-ticks 72000 --seed-offset 0
   ```
   (n_ticks 72,000 = 1h at 50 ms heartbeat → enables 1h degradation labels)

2. **Train 30 epochs** (≈30 min T4 GPU or ≈8h CPU):
   ```bash
   python predictor/train.py --data-dir data_full --out-dir model_full \
     --epochs 30 --n-train 80 --n-val 10 --n-test 10
   ```

3. **Acceptance check**: confirm all three pre-registered thresholds pass on
   `test_metrics.json`.

4. **Freeze model** to `model_full/best.pt`, ship into the S-Raft sidecar.

## Why this pivot is stronger than v25

| Axis | v25 (BRAO for Fabric ordering) | v26 (Score-Predictor) |
|---|---|---|
| AI role | Tx criticality prediction | Sub-leader Score replacement |
| AI removable? | Yes (heuristic substitute) | Yes, but Safety theorem makes removal trivially safe |
| Blockchain core touched? | No — orderer wrapper | Yes — consensus ranking function |
| One backbone, multiple uses? | No (oracle is single-purpose) | Yes — prediction + security + maintenance |
| Reviewer "why AI" question | "1-2% faster" | "Non-stationary network + future-state planning + audit-ready security" |

## Next steps (in order)

1. ☐ Generate full 320-trace dataset
2. ☐ 30-epoch training run, confirm acceptance thresholds
3. ☐ TLA+ Apalache encoding of integration rules + invariant proof
4. ☐ v26 manuscript draft (14p EN/KO) — integrate `paper_section_v26.tex`
5. ☐ Update AWS 5h experiment to compare {S-Raft baseline, +predict, +anomaly, +full}
6. ☐ Pre-register new hash for v26 experiment
7. ☐ Run + report

## Honest disclaimer

The dev run validates pipeline correctness, not paper claims. Full
acceptance pending data scale and training compute. All numbers in
`paper_section_v26.tex` (P99 inference 3 ms, 141K params, 0.56 MB) are
measured; performance metrics (RMSE thresholds, AUC targets) are
*pre-registered targets* awaiting full-scale validation.
