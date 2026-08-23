#!/usr/bin/env bash
# run_orchestrator.sh — Master wall-clock controller for the 5-hour run.
# Reads timeline.json, executes each phase, checks GO/NO-GO, aborts on failure.
#
# Usage: ./run_orchestrator.sh <run_id>

set -euo pipefail

RUN_ID="${1:?usage: $0 <run_id>}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="$ROOT/logs/$RUN_ID"
mkdir -p "$LOG_DIR"

START_TS=$(date +%s)
HARD_KILL_S=$((5 * 3600 + 30 * 60))  # T+5:30

log() { echo "[$(date -Iseconds)] $*" | tee -a "$LOG_DIR/orchestrator.log"; }

check_budget_kill() {
  local now=$(date +%s)
  local elapsed=$((now - START_TS))
  if [[ $elapsed -gt $HARD_KILL_S ]]; then
    log "HARD KILL: elapsed=${elapsed}s > ${HARD_KILL_S}s"
    abort
  fi
}

abort() {
  log "ABORT triggered. Snapshotting + tearing down."
  aws s3 sync /data "s3://schedulable-bft-$RUN_ID/runs/$RUN_ID/aborted/" || true
  cd "$ROOT/terraform" && terraform destroy -auto-approve -var "run_id=$RUN_ID" || true
  exit 1
}

trap abort ERR

# -----------------------------------------------------------------------------
# Pre-registration check — refuse to run if runbook hash drifted
# -----------------------------------------------------------------------------
log "Verifying pre-registration hash"
COMPUTED=$(bash "$ROOT/scripts/preregister.sh")
EXPECTED=$(cat "$ROOT/preregister.hash" 2>/dev/null || echo "MISSING")
if [[ "$COMPUTED" != "$EXPECTED" ]]; then
  log "PREREGISTER HASH MISMATCH: computed=$COMPUTED expected=$EXPECTED"
  log "Aborting — runbook contents drifted since preregister"
  exit 2
fi
log "Pre-register hash OK: $COMPUTED"

# -----------------------------------------------------------------------------
# T+0:00 — Provision
# -----------------------------------------------------------------------------
log "T+0:00 — terraform apply"
cd "$ROOT/terraform"
terraform init -input=false
terraform apply -auto-approve -var "run_id=$RUN_ID" -var-file=secrets.tfvars
terraform output -raw ansible_inventory > "$ROOT/ansible/inventory.yml"
check_budget_kill

# -----------------------------------------------------------------------------
# T+0:10 — Fabric bootstrap
# -----------------------------------------------------------------------------
log "T+0:10 — ansible bootstrap"
cd "$ROOT/ansible"
ansible-playbook -i inventory.yml playbooks/01_bootstrap.yml
check_budget_kill

# -----------------------------------------------------------------------------
# T+0:25 — Calibration
# -----------------------------------------------------------------------------
log "T+0:25 — calibration ping"
ssh -o StrictHostKeyChecking=no ubuntu@$(jq -r '.caliper_ip' /dev/null) \
    "cd /opt/caliper && npx caliper launch manager \
      --caliper-workspace . \
      --caliper-benchconfig /opt/runbook/caliper/calibration.yaml \
      --caliper-networkconfig /opt/fabric/network-config.yaml"
check_budget_kill

# -----------------------------------------------------------------------------
# Arms. The ladder is the one §V-C uses on a single host, so that the two sets
# of throughput numbers can be placed side by side:
#
#   E1  clean, advisor off        the reference condition
#   E2  +200 ms on orderer3       the attack, unguarded
#   E3  +200 ms on orderer3       the same attack, advisor active
#
# Only the orderer-side state changes between arms; the Caliper workload is
# identical in all three, which is what makes the comparison a comparison.
# -----------------------------------------------------------------------------
run_arm() {   # run_arm <tag>
    local tag=$1
    log "arm $tag — caliper"
    ssh ubuntu@$CALIPER_IP "cd /opt/caliper && npx caliper launch manager \
        --caliper-workspace . \
        --caliper-benchconfig /opt/runbook/caliper/benchmark-$tag.yaml \
        --caliper-networkconfig /opt/fabric/network-config.yaml"
    aws s3 sync /data/caliper s3://schedulable-bft-$RUN_ID/runs/$RUN_ID/$tag/
    check_budget_kill
}

# --- E1: clean, advisor off --------------------------------------------------
log "T+0:35 — E1 clean (advisor off, no delay)"
ansible-playbook -i inventory.yml playbooks/03_ablation_toggle.yml
ansible-playbook -i inventory.yml playbooks/04_netem_inject.yml -e state=off
run_arm e1

# --- E2: attack, advisor off -------------------------------------------------
log "T+1:35 — E2 attack (advisor off, +200 ms on orderer3)"
ansible-playbook -i inventory.yml playbooks/04_netem_inject.yml -e state=on
run_arm e2

# --- E3: attack, advisor active ----------------------------------------------
# The delay stays exactly as it was for E2; only the advisor comes up, so any
# difference between E2 and E3 is attributable to the advisor and not to a
# re-applied qdisc.
log "T+2:45 — E3 guarded (advisor active, delay unchanged)"
ansible-playbook -i inventory.yml playbooks/02_proposed_patch.yml
run_arm e3

# --- restore -----------------------------------------------------------------
log "removing delay injection"
ansible-playbook -i inventory.yml playbooks/04_netem_inject.yml -e state=off

# -----------------------------------------------------------------------------
# T+3:45 — Burst overlay
# -----------------------------------------------------------------------------
log "T+3:45 — Burst overlay"
ssh ubuntu@$CALIPER_IP "cd /opt/caliper && npx caliper launch manager \
    --caliper-workspace . \
    --caliper-benchconfig /opt/runbook/caliper/benchmark-burst.yaml \
    --caliper-networkconfig /opt/fabric/network-config.yaml"
aws s3 sync /data/caliper s3://schedulable-bft-$RUN_ID/runs/$RUN_ID/burst/
check_budget_kill

# -----------------------------------------------------------------------------
# T+4:15 — Analysis
# -----------------------------------------------------------------------------
log "T+4:15 — Analysis"
aws s3 sync "s3://schedulable-bft-$RUN_ID/runs/$RUN_ID/" "$LOG_DIR/data/"
python "$ROOT/analysis/aws_5h_analysis.py" \
    --data-root "$LOG_DIR/data" \
    --out-dir "$LOG_DIR/analysis" \
    --preregister-hash "$EXPECTED"
aws s3 sync "$LOG_DIR/analysis/" "s3://schedulable-bft-$RUN_ID/runs/$RUN_ID/analysis/"
check_budget_kill

# -----------------------------------------------------------------------------
# T+4:45 — Teardown
# -----------------------------------------------------------------------------
log "T+4:45 — Teardown"
aws s3 sync /data "s3://schedulable-bft-$RUN_ID/runs/$RUN_ID/raw/" || true
cd "$ROOT/terraform"
terraform destroy -auto-approve -var "run_id=$RUN_ID"

log "T+5:00 — Run complete. Report: $LOG_DIR/analysis/REPORT.md"
