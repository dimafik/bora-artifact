#!/usr/bin/env bash
# v3 pilot: one seed, one rate, short cells, both phases.
set -u
cd /mnt/d/fabric-d2 || exit 1
exec timeout 2400 bash alg1/r13_v3.sh 7 1 120 20 \
  > /mnt/d/fabric-d2/results/r13_v3_pilot.log 2>&1
