#!/usr/bin/env bash
# Wait for the in-flight low/mid load sweep to finish, then run the high-load
# extension to find the degradation knee. Robust dir resolution inside the loop.
set -u
echo "[chain] waiting for current load sweep to finish..."
while true; do
  D=$(ls -dt /mnt/d/fabric-d2/results/loadsweep_* 2>/dev/null | head -1)
  if [ -n "$D" ] && grep -q "LOAD_SWEEP_DONE" "$D/summary.txt" 2>/dev/null; then
    echo "[chain] low/mid sweep done: $D"
    cat "$D/results.csv"
    break
  fi
  sleep 10
done
echo "[chain] starting HIGH-LOAD extension (450 550 650)..."
LOADS="450 550 650" K=8 bash /mnt/d/fabric-d2/alg1/load_sweep.sh
echo "[chain] HIGH-LOAD done."
