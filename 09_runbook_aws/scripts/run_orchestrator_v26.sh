#!/usr/bin/env bash
# run_orchestrator_v26.sh -- v26 4-arm S-Raft live experiment orchestrator.
# Refuses to run unless preregister.hash matches the current state.
#
# Usage: bash run_orchestrator_v26.sh <run_id>

set -euo pipefail

RUN_ID="${1:?usage: $0 <run_id>}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$ROOT/logs/$RUN_ID"
DATA_DIR="$LOG_DIR/data"
mkdir -p "$DATA_DIR"

START_TS=$(date +%s)
HARD_KILL_S=$((5 * 3600 + 30 * 60))

log() { echo "[$(date -Iseconds)] $*" | tee -a "$LOG_DIR/orchestrator.log"; }
abort() {
    log "ABORT"
    aws s3 sync "$DATA_DIR" "s3://schedulable-bft-$RUN_ID/runs/$RUN_ID/aborted/" || true
    (cd "$ROOT/terraform" && terraform destroy -auto-approve -var "run_id=$RUN_ID") || true
    exit 1
}
trap abort ERR

# ----- Preregister gate -----
log "Verifying preregister hash"
COMPUTED=$(bash "$ROOT/scripts/preregister.sh")
EXPECTED=$(cat "$ROOT/preregister.hash")
if [[ "$COMPUTED" != "$EXPECTED" ]]; then
    log "HASH MISMATCH: $COMPUTED != $EXPECTED"
    exit 2
fi

# ----- Provision -----
log "T+0:00 terraform apply"
cd "$ROOT/terraform"
terraform init -input=false
terraform apply -auto-approve -var "run_id=$RUN_ID" -var-file=secrets.tfvars
terraform output -json | jq -r '.ip_map.value' > "$DATA_DIR/inventory.json"

# ----- Bootstrap -----
log "T+0:10 ansible bootstrap"
cd "$ROOT/ansible"
ansible-playbook -i "$DATA_DIR/inventory.json" playbooks/01_bootstrap_sraft.yml

# ----- Calibration -----
log "T+0:25 calibration"
ansible-playbook -i "$DATA_DIR/inventory.json" playbooks/calibrate.yml

# ----- Helper -----
run_arm() {
    local arm=$1
    local arm_start=$2
    log "T+$arm_start arm $arm: 50-min failure injection + Byzantine overlay last 10 min"
    python "$ROOT/scripts/failure_injector.py" \
        --arm "$arm" \
        --inventory "$DATA_DIR/inventory.json" \
        --out-file "$DATA_DIR/arm_${arm,,}_events.json" \
        --seed 42 &
    INJ_PID=$!

    # 40 min into the arm, start Byzantine overlay (10 min duration)
    sleep $((40 * 60))
    python "$ROOT/scripts/byzantine_overlay.py" \
        --inventory "$DATA_DIR/inventory.json" \
        --byz-node node3 \
        --duration-s 600 \
        --out-file "$DATA_DIR/arm_${arm,,}_byz.json"
    wait $INJ_PID

    # Sync sidecar telemetry
    ansible -i "$DATA_DIR/inventory.json" orderers \
        -m fetch -a "src=/var/log/sidecar/anomaly.parquet dest=$DATA_DIR/arm_${arm,,}_sidecar/"
}

# ----- Arm A: baseline -----
ansible-playbook -i "$DATA_DIR/inventory.json" playbooks/set_advice.yml -e "predict=0 anomaly=0 degrade=0"
run_arm A "0:35"

# ----- Arm B: prediction -----
ansible-playbook -i "$DATA_DIR/inventory.json" playbooks/set_advice.yml -e "predict=1 anomaly=0 degrade=0"
run_arm B "1:25"

# ----- Arm C: prediction + anomaly -----
ansible-playbook -i "$DATA_DIR/inventory.json" playbooks/set_advice.yml -e "predict=1 anomaly=1 degrade=0"
run_arm C "2:15"

# ----- Arm D: full ML -----
ansible-playbook -i "$DATA_DIR/inventory.json" playbooks/set_advice.yml -e "predict=1 anomaly=1 degrade=1"
run_arm D "3:05"

# ----- GC-stall injection (was concurrent during arm B-D middle 20 min) -----
ansible-playbook -i "$DATA_DIR/inventory.json" playbooks/inject_gc_stalls.yml \
    -e "n_stalls=5 duration_ms_min=600 duration_ms_max=1500" \
    -e "out_path=$DATA_DIR/gc_stalls.json"

# ----- Analysis -----
log "T+4:10 analysis"
python "$ROOT/analysis/aws_v26_analysis.py" \
    --data-dir "$DATA_DIR" \
    --out-dir "$LOG_DIR/results" \
    --preregister-hash "$EXPECTED"

# ----- Teardown -----
log "T+4:45 teardown"
aws s3 sync "$DATA_DIR" "s3://schedulable-bft-$RUN_ID/runs/$RUN_ID/raw/"
aws s3 sync "$LOG_DIR/results" "s3://schedulable-bft-$RUN_ID/runs/$RUN_ID/results/"
cd "$ROOT/terraform"
terraform destroy -auto-approve -var "run_id=$RUN_ID"

log "T+5:00 done. REPORT: $LOG_DIR/results/results.json"
