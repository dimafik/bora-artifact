#!/usr/bin/env bash
# Re-run the p=20 block only (9 cells) after the first full run was cut off by
# its own 5-hour timeout at 34/36.  p=20 is the block where false positives
# coincide with a forced election most often, so it carries most of the evidence
# for the liveness observation -- it is the one block worth having complete.
#
# Timeout is 2 h for ~80 min of work.  The previous run allowed 5 h for ~4.8 h,
# which left no margin and killed the script mid-cell, leaving an orderer paused.
set -u
cd /mnt/d/fabric-d2 || exit 1
exec timeout 7200 bash alg1/r13_v2.sh 7 3 300 20 \
  > /mnt/d/fabric-d2/results/r13_v2_p20.log 2>&1
