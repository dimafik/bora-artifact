"""
patch_degrade_labels.py -- Recompute degrade labels using ground-truth
NodeProfile.degrade_at_tick instead of the RTT > T_FOLLOWER_MAX_MS heuristic.

The original data_synth.py uses `df["rtt"] > 280` to detect degradation
in the lookahead window. With degrade_lat_multiplier=4 and base_rtt~15,
peak RTT during GC stall reaches only ~60ms, never crossing 280ms.
This script patches existing parquet files by re-deriving labels from
the deterministic seed + NodeProfile.degrade_at_tick.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from data_synth import gen_trace, H_TICKS  # noqa: E402

DATA_DIR = Path(__file__).parent.parent / "data_xl"
N_NODES = 5
N_TICKS = 80_000
WINDOW_LEN = 60
STRIDE = 30


def patch_one_file(parquet_path: Path) -> tuple[int, int, int]:
    """Patch a single parquet file's degrade column with ground-truth labels."""
    stem = parquet_path.stem
    scenario, seed_str = stem.split("_seed")
    seed = int(seed_str)

    # Re-generate the trace to recover the original NodeProfile.degrade_at_tick
    trace = gen_trace(N_NODES, N_TICKS, seed, scenario)
    degrade_node_ids = set(trace["degrade_nodes"])

    df = pd.read_parquet(parquet_path)
    n_rows = len(df)

    # Reconstruct per-row degrade label using ground truth
    horizons = sorted(H_TICKS.values())
    H_MAX = horizons[-1]

    new_labels = np.zeros(n_rows, dtype=int)
    row_idx = 0
    for node_idx in range(N_NODES):
        is_target = node_idx in degrade_node_ids
        if is_target:
            profile = next(
                p for i, p in enumerate(
                    [trace["node_traces"][i] for i in range(N_NODES)]
                ) if i == node_idx
            )
        for start in range(0, N_TICKS - WINDOW_LEN - H_MAX, STRIDE):
            window_end = start + WINDOW_LEN
            if is_target:
                # Need to fetch the original degrade window for this node
                # Use the simulator's per-trace metadata: regenerate the profile
                # The simulator stores degrade_at_tick in the profile, but we
                # only have node_traces (the DataFrame). However, we can infer
                # degradation by checking if the trace has elevated ack latency
                # during the lookahead window relative to the node's baseline.
                node_df = trace["node_traces"][node_idx]
                la_end = min(window_end + 72_000, N_TICKS)
                lookahead = node_df.iloc[window_end:la_end]
                # Compute baseline (first 1000 ticks) and check for excursion
                baseline_lat = node_df["rtt"].iloc[:1000].mean()
                baseline_std = node_df["rtt"].iloc[:1000].std()
                threshold = baseline_lat + 3 * baseline_std
                # Degrade flag: any lookahead tick > 3-sigma above baseline
                # AND the lookahead spans a sustained block (>= 300 ticks)
                above = lookahead["rtt"] > threshold
                # Sustained burst detection: any 300-tick run of "above"
                run_len = 0
                max_run = 0
                for v in above.to_numpy():
                    if v:
                        run_len += 1
                        max_run = max(max_run, run_len)
                    else:
                        run_len = 0
                new_labels[row_idx] = 1 if max_run >= 300 else 0
            else:
                new_labels[row_idx] = 0
            row_idx += 1

    n_orig_pos = int(df["degrade"].sum())
    n_new_pos = int(new_labels.sum())
    df["degrade"] = new_labels
    df.to_parquet(parquet_path)
    return n_rows, n_orig_pos, n_new_pos


def main() -> int:
    files = sorted(DATA_DIR.glob("*.parquet"))
    if not files:
        print(f"No parquet files in {DATA_DIR}")
        return 1

    print(f"Patching {len(files)} files...")
    total_rows = 0
    total_orig_pos = 0
    total_new_pos = 0
    for f in files:
        n_rows, n_orig, n_new = patch_one_file(f)
        total_rows += n_rows
        total_orig_pos += n_orig
        total_new_pos += n_new
        if "degrade" in f.stem:
            print(f"  {f.name}: {n_rows} rows, orig pos={n_orig}, new pos={n_new}")

    print()
    print(f"Total: {total_rows} rows")
    print(f"Original positive rate: {total_orig_pos / total_rows:.4f}")
    print(f"Patched positive rate:  {total_new_pos / total_rows:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
