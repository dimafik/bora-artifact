#!/usr/bin/env bash
# High-load extension of the load sweep to capture the degradation knee near
# and above the ~570 tx/s commit ceiling.
export LOADS="450 550 650"
export K=8
bash /mnt/d/fabric-d2/alg1/load_sweep.sh
