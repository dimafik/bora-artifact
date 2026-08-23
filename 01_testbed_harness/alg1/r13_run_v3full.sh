#!/usr/bin/env bash
# v3 full run: phase 1 (36 cells) + phase 2 (6 cells) ~ 5h20m.
# Timeout is 7.5 h -- the v2 run allowed 5 h for 4.8 h of work, and when it
# expired mid-cell it left an orderer paused, which then faked a liveness result.
set -u
cd /mnt/d/fabric-d2 || exit 1
exec timeout 27000 bash alg1/r13_v3.sh 7 3 300 0 5 10 20 \
  > /mnt/d/fabric-d2/results/r13_v3_full.log 2>&1
