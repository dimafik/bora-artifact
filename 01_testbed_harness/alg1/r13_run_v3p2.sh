#!/usr/bin/env bash
# Phase-2-only pilot: skip phase 1 by passing an empty rate list is not possible,
# so run phase 1 with a single 30 s cell and let phase 2 do the real work.
set -u
cd /mnt/d/fabric-d2 || exit 1
exec timeout 3000 bash alg1/r13_v3.sh 7 2 30 0 \
  > /mnt/d/fabric-d2/results/r13_v3_p2pilot.log 2>&1
