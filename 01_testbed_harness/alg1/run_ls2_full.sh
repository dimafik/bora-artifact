#!/usr/bin/env bash
# Master orchestration: fresh network -> BORA binary -> sidecar -> LS2 experiment.
set -u
export PATH=/home/jinu337/go-install/bin:/mnt/d/fabric-d2/fabric-samples/bin-linux/bin:/usr/local/bin:/usr/bin:/bin
LOG=/mnt/d/fabric-d2/results/ls2_master_$(date +%Y%m%d-%H%M%S).log
exec > >(tee "$LOG") 2>&1
echo "MASTER_LOG=$LOG"

echo "================ STEP 1/4: fresh network ================"
bash /mnt/d/fabric-d2/fresh-network.sh
if ! docker ps --format '{{.Names}}' | grep -q orderer3.example.com; then
  echo "STEP1_FAIL: orderer3 not up"; exit 1
fi
echo "[step1] settle 15s"; sleep 15

echo "================ STEP 2/4: deploy BORA orderer binary ================"
bash /mnt/d/fabric-d2/alg1/deploy_bora_v3.sh
echo "[step2] settle 12s"; sleep 12

echo "================ STEP 3/4: deploy sidecar ================"
bash /mnt/d/fabric-d2/alg1/deploy_sidecar.sh
if ! docker exec orderer.example.com sh -c 'test -S /var/run/raft-advisor.sock'; then
  echo "STEP3_FAIL: sidecar socket missing on orderer1"; exit 1
fi

echo "================ STEP 4/4: LS2 experiment ================"
ATTACK_MS=500 N_ELECT=12 bash /mnt/d/fabric-d2/alg1/leader_scenario_v2.sh
echo "RUN_LS2_FULL_DONE"
