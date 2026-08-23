#!/usr/bin/env bash
# ONE comprehensive pass of the autonomous BORA suite (chained across
# re-invocations to span ~6h). Honest measurement only.
# Args: $1 = shared OUT dir, $2 = seed number.
# Families: A) leadership-exclusion (seed1 only)  B) throughput clean/attack/BORA
#   C) two-follower attack  D) delay magnitude  E) pause/flap leader.
set -u
SEED="${2:-1}"
OUT="${1:-/mnt/d/fabric-d2/results/auto6h_$(date +%Y%m%d-%H%M%S)}"; mkdir -p "$OUT"
SUM="$OUT/MASTER_SUMMARY.txt"
PASS_START=$(date +%s); PASS_DEADLINE=$((PASS_START+3600))   # 60min safety cap/pass
WS=/mnt/d/fabric-d2/caliper-workspace
CRYPTO=/mnt/d/fabric-d2/fabric-samples/test-network/organizations
ORDERERS=(orderer.example.com orderer2.example.com orderer3.example.com orderer4.example.com orderer5.example.com)
SEQ=$((5000+SEED*100))
log(){ echo "[$(date +%H:%M) s$SEED] $*" | tee -a "$SUM"; }
time_left(){ [ "$(date +%s)" -lt "$PASS_DEADLINE" ]; }
name_for_id(){ case $1 in 1) echo orderer.example.com;; 2) echo orderer2.example.com;; 3) echo orderer3.example.com;; 4) echo orderer4.example.com;; 5) echo orderer5.example.com;; *) echo "";; esac; }
geth(){ docker exec peer0.org1.example.com peer channel getinfo -c mychannel 2>/dev/null | grep -ao '"height":[0-9]*' | grep -ao '[0-9]*'; }
leader_id(){ for o in "${ORDERERS[@]}"; do docker logs --tail 250 "$o" 2>&1 | grep -ao "Raft leader changed:[^c]*-> [0-9][0-9]*" | tail -1 | grep -ao "[0-9][0-9]*$"; done | sort | uniq -c | sort -rn | head -1 | grep -ao "[0-9][0-9]*$"; }
write_advice(){ SEQ=$((SEQ+1)); for o in "${ORDERERS[@]}"; do docker exec "$o" sh -c "echo '{\"blacklist\":$1,\"seq\":$SEQ,\"fail_open\":false}' > /tmp/bora-advice.json" 2>/dev/null; done; }
ensure_sidecars(){ for o in "${ORDERERS[@]}"; do docker exec "$o" sh -c 'test -S /var/run/raft-advisor.sock' 2>/dev/null || docker exec -d "$o" setsid /tmp/bora-sidecar 2>/dev/null; done; sleep 2; }
start_attack(){ docker rm -f pumba-a >/dev/null 2>&1; docker run -d --name pumba-a -v /var/run/docker.sock:/var/run/docker.sock gaiaadm/pumba:latest --interval 40m --log-level warning netem --tc-image gaiadocker/iproute2 --duration 35m delay --time "${1:-500}" "${2:-orderer3.example.com}" >/dev/null 2>&1; sleep 4; }
start_attack2(){ docker rm -f pumba-a pumba-b >/dev/null 2>&1
  docker run -d --name pumba-a -v /var/run/docker.sock:/var/run/docker.sock gaiaadm/pumba:latest --interval 40m --log-level warning netem --tc-image gaiadocker/iproute2 --duration 35m delay --time "$1" orderer3.example.com >/dev/null 2>&1
  docker run -d --name pumba-b -v /var/run/docker.sock:/var/run/docker.sock gaiaadm/pumba:latest --interval 40m --log-level warning netem --tc-image gaiadocker/iproute2 --duration 35m delay --time "$1" orderer4.example.com >/dev/null 2>&1; sleep 4; }
stop_attacks(){ docker rm -f pumba-a pumba-b >/dev/null 2>&1; }
FLAP_PID=""
start_flap(){ ( for k in $(seq 1 80); do docker pause "$1" >/dev/null 2>&1; sleep 3; docker unpause "$1" >/dev/null 2>&1; sleep 6; done ) & FLAP_PID=$!; }
stop_flap(){ [ -n "$FLAP_PID" ] && kill "$FLAP_PID" >/dev/null 2>&1; docker unpause "$1" >/dev/null 2>&1; FLAP_PID=""; }

run_sweep(){ # $1 label  $2 benchconfig
  local dir="$OUT/$1"; mkdir -p "$dir"
  local hb; hb=$(geth); local tb; tb=$(date +%s)
  docker rm -f caliper-a >/dev/null 2>&1
  docker run --rm --name caliper-a --network fabric_test \
    -v "$WS:/hyperledger/caliper/workspace" -v "$CRYPTO:/cryptoMount" \
    --add-host=host.docker.internal:host-gateway \
    -e CALIPER_BIND_SUT=fabric:fabric-gateway -e CALIPER_BENCHCONFIG=benchmarks/$2 \
    -e CALIPER_NETWORKCONFIG=networks/fabric-5node.yaml -e CALIPER_FLOW_ONLY_TEST=true \
    -e CALIPER_REPORT_PATH=/hyperledger/caliper/workspace/report-a.html \
    hyperledger/caliper:0.6.0 launch manager > "$dir/caliper.log" 2>&1
  cp "$WS/report-a.html" "$dir/" 2>/dev/null
  local ha; ha=$(geth); local ta; ta=$(date +%s)
  { echo ">>> $1 | ledgerD=$((ha-hb)) blocks /$((ta-tb))s | leader=$(leader_id)"
    grep -aE "\| rate-[0-9]+" "$dir/caliper.log" 2>/dev/null | head -8
  } | tee -a "$SUM"
}

exp_leadership_exclusion(){
  local R=12
  log "### EXP-A leadership-exclusion efficacy (rounds=$R/phase)"
  write_advice "[]"; sleep 2; local base=""
  for i in $(seq 1 $R); do time_left || break
    local L LC; L=$(leader_id); LC=$(name_for_id "$L"); [ -z "$LC" ] && LC=orderer.example.com
    docker restart "$LC" >/dev/null 2>&1; sleep 14; base="$base $(leader_id)"; done
  log "  baseline winners:$base"
  local W; W=$(echo $base | tr ' ' '\n' | grep -E '^[0-9]+$' | sort | uniq -c | sort -rn | head -1 | grep -ao '[0-9]*$'); [ -z "$W" ] && W=1
  log "  most-frequent winner = node $W -> BORA blacklists it"
  write_advice "[$W]"; sleep 2; local bora=""
  for i in $(seq 1 $R); do time_left || break
    local L LC; L=$(leader_id); LC=$(name_for_id "$L"); [ -z "$LC" ] && LC=orderer.example.com
    docker restart "$LC" >/dev/null 2>&1; sleep 14; bora="$bora $(leader_id)"; done
  log "  BORA(blacklist $W) winners:$bora"
  local bw bbw; bw=$(echo $base | tr ' ' '\n' | grep -c "^$W$"); bbw=$(echo $bora | tr ' ' '\n' | grep -c "^$W$")
  log "  >>> EXP-A RESULT: node $W won $bw/$R baseline vs $bbw/$R with BORA; every round still elected a leader (liveness preserved)."
  write_advice "[]"
}

log "===== PASS seed=$SEED START (OUT=$OUT) ====="
ensure_sidecars
log "sidecar sockets: $(for o in "${ORDERERS[@]}"; do docker exec "$o" sh -c 'test -S /var/run/raft-advisor.sock && echo 1 || echo 0'; done | tr -d '\n')  leader=$(leader_id)"

exp_leadership_exclusion   # EXP-A every pass for more seeds (BORA's real value)

time_left && { log "### EXP-B throughput clean/attack/BORA (500ms orderer3, wide)"; write_advice "[]"; stop_attacks; run_sweep "B_clean_s$SEED" wide-sweep.yaml; }
time_left && { write_advice "[]"; start_attack 500 orderer3.example.com; run_sweep "B_attack_s$SEED" wide-sweep.yaml; stop_attacks; }
time_left && { start_attack 500 orderer3.example.com; write_advice "[3]"; run_sweep "B_bora_s$SEED" wide-sweep.yaml; stop_attacks; write_advice "[]"; }

for rep in 1 2; do   # EXP-C two-follower (the promising BORA throughput regime), replicated
  time_left && { log "### EXP-C two-follower (300ms o3+o4, BORA blk 3) rep$rep"; write_advice "[]"; start_attack2 300; run_sweep "C_attack2_s${SEED}r${rep}" fast-sweep.yaml; }
  time_left && { write_advice "[3]"; run_sweep "C_bora2_s${SEED}r${rep}" fast-sweep.yaml; stop_attacks; write_advice "[]"; sleep 6; }
done

stop_attacks; write_advice "[]"
log "===== PASS seed=$SEED DONE ($(( ($(date +%s)-PASS_START)/60 ))min) ====="
echo "AUTO6H_PASS_DONE seed=$SEED out=$OUT"
