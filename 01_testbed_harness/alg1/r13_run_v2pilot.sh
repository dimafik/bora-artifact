#!/usr/bin/env bash
# Zero-argument pilot for the v2 design (see r13_run_full.sh for why no args).
set -u
cd /mnt/d/fabric-d2 || exit 1
exec timeout 1500 bash alg1/r13_v2.sh 7 1 120 20 \
  > /mnt/d/fabric-d2/results/r13_v2_pilot.log 2>&1
