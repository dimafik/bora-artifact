#!/usr/bin/env bash
set -u
cd /mnt/d/fabric-d2 || exit 1
exec timeout 5400 bash alg1/r13_p2b.sh 7 3 5 \
  > /mnt/d/fabric-d2/results/r13_p2b.log 2>&1
