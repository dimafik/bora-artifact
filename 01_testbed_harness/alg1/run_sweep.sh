#!/usr/bin/env bash
# Run the remaining X1 N-sweep end to end, one N at a time.
#
# Replaces the nested background chains that produced the N=9 failure. Each N is
# gated twice and the sweep STOPS on the first failure rather than carrying a
# broken predictor into the next hour of measurements:
#
#   1. start_daemon.sh waits for the daemon's own start banner for this N
#   2. x1_closedloop.sh re-checks bt.json freshness and cap against this N's f
#      before it spends twelve minutes on bring-up
#
#   run_sweep.sh "9 4" "15 7" "21 10"
set -u
set -o pipefail

A=/mnt/d/fabric-d2/alg1
R=/mnt/d/fabric-d2/results
SEEDS="${SEEDS:-4}"; NE="${NE:-10}"; DLY="${DLY:-200}"

for spec in "$@"; do
  set -- $spec
  N="$1"; F="$2"
  echo "=============================================================="
  echo "N=$N f=$F   seeds=$SEEDS elec=$NE delay=${DLY}ms   $(date +%H:%M:%S)"
  echo "=============================================================="

  if ! bash "$A/start_daemon.sh" "$N" "$F"; then
    echo "SWEEP ABORT: daemon would not start for N=$N"
    exit 1
  fi

  if ! bash "$A/x1_closedloop.sh" "$N" "$SEEDS" "$NE" "$DLY" 2>&1 | tee "$R/x1_main_N${N}.out"; then
    echo "SWEEP ABORT: run failed at N=$N (see $R/x1_main_N${N}.out)"
    exit 1
  fi

  grep -q "X1_N${N}_DONE" "$R/x1_main_N${N}.out" || {
    echo "SWEEP ABORT: N=$N produced no completion marker"; exit 1; }
  echo "N=$N complete $(date +%H:%M:%S)"
done

echo "SWEEP_COMPLETE $(date +%H:%M:%S)"
