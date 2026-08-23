#!/usr/bin/env bash
ROOT=/mnt/d/fabric-d2/results/ne26_v3_20260610-144753
for ph in phaseA_clean phaseB_attack; do
  for s in 1 2 3; do
    echo "=== $ph seed$s ==="
    cat "$ROOT/$ph/seed$s/conc_sweep/summary.csv" 2>/dev/null
  done
done
