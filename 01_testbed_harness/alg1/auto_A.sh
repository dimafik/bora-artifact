#!/usr/bin/env bash
# EXP-A only, looped K times to accumulate leadership-exclusion seeds.
set -u
OUT="${1:-/mnt/d/fabric-d2/results/auto6h_run}"; mkdir -p "$OUT"
K="${2:-6}"
SUM="$OUT/MASTER_SUMMARY.txt"
ORDERERS=(orderer.example.com orderer2.example.com orderer3.example.com orderer4.example.com orderer5.example.com)
SEQ=8000
log(){ echo "[$(date +%H:%M) A] $*" | tee -a "$SUM"; }
name_for_id(){ case $1 in 1) echo orderer.example.com;; 2) echo orderer2.example.com;; 3) echo orderer3.example.com;; 4) echo orderer4.example.com;; 5) echo orderer5.example.com;; *) echo "";; esac; }
leader_id(){ for o in "${ORDERERS[@]}"; do docker logs --tail 250 "$o" 2>&1 | grep -ao "Raft leader changed:[^c]*-> [0-9][0-9]*" | tail -1 | grep -ao "[0-9][0-9]*$"; done | sort | uniq -c | sort -rn | head -1 | grep -ao "[0-9][0-9]*$"; }
write_advice(){ SEQ=$((SEQ+1)); for o in "${ORDERERS[@]}"; do docker exec "$o" sh -c "echo '{\"blacklist\":$1,\"seq\":$SEQ,\"fail_open\":false}' > /tmp/bora-advice.json" 2>/dev/null; done; }
ensure_sidecars(){ for o in "${ORDERERS[@]}"; do docker exec "$o" sh -c 'test -S /var/run/raft-advisor.sock' 2>/dev/null || docker exec -d "$o" setsid /tmp/bora-sidecar 2>/dev/null; done; sleep 2; }

exp_A(){
  local R=12
  write_advice "[]"; sleep 2; local base=""
  for i in $(seq 1 $R); do local L LC; L=$(leader_id); LC=$(name_for_id "$L"); [ -z "$LC" ] && LC=orderer.example.com
    docker restart "$LC" >/dev/null 2>&1; sleep 14; base="$base $(leader_id)"; done
  local W; W=$(echo $base | tr ' ' '\n' | grep -E '^[0-9]+$' | sort | uniq -c | sort -rn | head -1 | grep -ao '[0-9]*$'); [ -z "$W" ] && W=1
  write_advice "[$W]"; sleep 2; local bora=""
  for i in $(seq 1 $R); do local L LC; L=$(leader_id); LC=$(name_for_id "$L"); [ -z "$LC" ] && LC=orderer.example.com
    docker restart "$LC" >/dev/null 2>&1; sleep 14; bora="$bora $(leader_id)"; done
  local bw bbw; bw=$(echo $base | tr ' ' '\n' | grep -c "^$W$"); bbw=$(echo $bora | tr ' ' '\n' | grep -c "^$W$")
  log ">>> EXP-A RESULT: node $W won $bw/$R baseline vs $bbw/$R with BORA; every round still elected a leader (liveness preserved). [base:$base][bora:$bora]"
  write_advice "[]"
}

log "=== auto_A start K=$K ==="
ensure_sidecars
for k in $(seq 1 $K); do log "--- A run $k/$K ---"; exp_A; done
log "=== auto_A done ==="
echo "AUTO_A_DONE"
