#!/usr/bin/env bash
# Remaining two measurements, in sequence.
#
# Throughput first because it is the shorter of the two and does not depend on
# the detector; the closed-loop arm then has the cluster to itself.  They must
# not overlap: both drive tc sidecars over the same orderers, and the closed
# loop additionally reads live RTT, which the other one's injected delays would
# corrupt.
set -u

LOG=/d/fabric-d2/results/potency/stage3_$(date +%Y%m%d-%H%M%S).log
exec > >(tee -a "$LOG") 2>&1

echo "######## throughput, m500, 180 s per condition, 4 tx/s offered ########"
bash /d/fabric-d2/alg1/potency_throughput.sh m500 180 4 1.0 || echo "TPUT_FAILED"

sleep 30

echo
echo "######## closed loop, m8, 40 elections per condition ########"
bash /d/fabric-d2/alg1/potency_closed.sh 40 || echo "CLOSED_FAILED"

echo "STAGE3_DONE"
