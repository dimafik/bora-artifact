#!/bin/bash
# Master script: run κ (Alg1 simulation) → ι (failover time) → μ (extended concurrency) sequentially
# Each starts on a fresh 5-orderer network
set -e

MASTER_LOG=/mnt/d/fabric-d2/master-kappa-iota-mu.log
echo "===== START $(date -Iseconds) =====" > "$MASTER_LOG"

run_phase() {
  local name=$1
  local script=$2
  echo "" | tee -a "$MASTER_LOG"
  echo "##################################################" | tee -a "$MASTER_LOG"
  echo "############ PHASE $name START ###################" | tee -a "$MASTER_LOG"
  echo "##################################################" | tee -a "$MASTER_LOG"
  date -Iseconds | tee -a "$MASTER_LOG"
  bash "$script" 2>&1 | tee -a "$MASTER_LOG"
  echo "PHASE $name DONE: $(date -Iseconds)" | tee -a "$MASTER_LOG"
}

# κ: Algorithm 1 simulation (will internally call fresh-network.sh)
run_phase "kappa" /mnt/d/fabric-d2/algorithm1-simulation.sh

# ι: Failover time (operates on existing network from κ, which has orderer3 stopped+restarted)
# Need to rebuild fresh
echo "" | tee -a "$MASTER_LOG"
echo "[Rebuilding fresh network before ι]" | tee -a "$MASTER_LOG"
bash /mnt/d/fabric-d2/fresh-network.sh 2>&1 | tail -3 | tee -a "$MASTER_LOG"

run_phase "iota" /mnt/d/fabric-d2/failover-time.sh

# μ: Extended concurrency C=32, 64
echo "" | tee -a "$MASTER_LOG"
echo "[Rebuilding fresh network before μ]" | tee -a "$MASTER_LOG"
bash /mnt/d/fabric-d2/fresh-network.sh 2>&1 | tail -3 | tee -a "$MASTER_LOG"

echo "" | tee -a "$MASTER_LOG"
echo "##################################################" | tee -a "$MASTER_LOG"
echo "############ PHASE mu START ######################" | tee -a "$MASTER_LOG"
echo "##################################################" | tee -a "$MASTER_LOG"
date -Iseconds | tee -a "$MASTER_LOG"

RESULTS=/mnt/d/fabric-d2/results_mu
mkdir -p "$RESULTS"
# Use a modified version of concurrency-sweep that includes C=32 and C=64
for s in 1 2 3; do
  echo "=== μ SEED $s ===" | tee -a "$MASTER_LOG"
  bash /mnt/d/fabric-d2/concurrency-sweep-v3-extended.sh "$s" 10 "$RESULTS" | tee -a "$MASTER_LOG"
done

echo "PHASE mu DONE: $(date -Iseconds)" | tee -a "$MASTER_LOG"

echo "" | tee -a "$MASTER_LOG"
echo "===== ALL PHASES DONE $(date -Iseconds) =====" | tee -a "$MASTER_LOG"
