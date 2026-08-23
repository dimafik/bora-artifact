#!/usr/bin/env bash
# Zero-argument full run for the v2 design.
# 4 rates x 3 seeds x 3 arms x 300 s, plus calibration ~ 3.5 h.
set -u
cd /mnt/d/fabric-d2 || exit 1
exec timeout 18000 bash alg1/r13_v2.sh 7 3 300 0 5 10 20 \
  > /mnt/d/fabric-d2/results/r13_v2_full.log 2>&1
