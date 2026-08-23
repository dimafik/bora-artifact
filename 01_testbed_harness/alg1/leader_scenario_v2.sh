#!/usr/bin/env bash
# ============================================================================
# BORA leadership-integrity experiment v2 (LS2)
#
# Fixes the two defects of leader_scenario.sh:
#   (1) Unreliable leader pinning -> robust 25-try pin verified by log.
#   (2) One-shot advice (seq gate made suppression last a single tick) ->
#       a BACKGROUND advice refresher bumps seq faster than the 500ms Raft
#       tick, so orderer3's election-tick suppression is SUSTAINED.
#
# Scenario: orderer3 is delay-attacked (+ATTACK_MS). We compare, under the
# SAME attack, two conditions that differ ONLY by whether BORA is advising:
#
#   A (no BORA, blacklist=[]):  orderer3 can win/hold leadership. We measure
#       its forced-election win rate, then PIN it as the (slow) leader and run
#       a sub-ceiling confirmed-commit sweep -> degraded throughput.
#   B (BORA, blacklist=[3] sustained): orderer3 is excluded from leadership.
#       We measure its forced-election win rate (-> ~0), then run the same
#       sweep with whatever HEALTHY node Raft elects -> recovered throughput.
#
# All throughput is confirmed-commit (Succ>0) at 100-500 tps, BELOW the
# ~570 tps single-host ceiling, cross-checked against ledger block-height.
# ============================================================================
set -u
ATTACK_MS="${ATTACK_MS:-500}"
N_ELECT="${N_ELECT:-12}"
WS=/mnt/d/fabric-d2/caliper-workspace
CRYPTO=/mnt/d/fabric-d2/fabric-samples/test-network/organizations
OUT=/mnt/d/fabric-d2/results/leaderscn2_$(date +%Y%m%d-%H%M%S); mkdir -p "$OUT"
ORDERERS=(orderer.example.com orderer2.example.com orderer3.example.com orderer4.example.com orderer5.example.com)
BL_FILE="$OUT/blacklist.json"; echo "[]" > "$BL_FILE"
SEQ_FILE="$OUT/seq.txt"; echo 2000 > "$SEQ_FILE"
RUN_FLAG="$OUT/refresh.on"; touch "$RUN_FLAG"

name_for_id(){ case $1 in 1) echo orderer.example.com;; 2) echo orderer2.example.com;; 3) echo orderer3.example.com;; 4) echo orderer4.example.com;; 5) echo orderer5.example.com;; *) echo "";; esac; }
leader_id(){ docker logs --tail 400 orderer.example.com 2>&1 | grep -ao "Raft leader changed:[^c]*-> [0-9][0-9]*" | tail -1 | grep -ao "[0-9][0-9]*$"; }
geth(){ docker exec peer0.org1.example.com peer channel getinfo -c mychannel 2>/dev/null | grep -ao '"height":[0-9]*' | grep -ao '[0-9]*'; }

# --- background advice refresher: bumps seq ~every 0.3s so suppression sticks
refresher(){
  while [ -f "$RUN_FLAG" ]; do
    local bl; bl=$(cat "$BL_FILE")
    local s; s=$(( $(cat "$SEQ_FILE") + 1 )); echo "$s" > "$SEQ_FILE"
    for o in "${ORDERERS[@]}"; do
      docker exec "$o" sh -c "echo '{\"blacklist\":$bl,\"seq\":$s,\"fail_open\":false}' > /tmp/bora-advice.json" 2>/dev/null &
    done
    wait
    sleep 0.25
  done
}
set_blacklist(){ echo "$1" > "$BL_FILE"; sleep 1; }   # let refresher propagate

start_attack(){ docker rm -f pumba-l2 >/dev/null 2>&1 || true
  docker run -d --name pumba-l2 -v /var/run/docker.sock:/var/run/docker.sock gaiaadm/pumba:latest \
    --interval 40m --log-level warning netem --tc-image gaiadocker/iproute2 --duration 35m \
    delay --time "$ATTACK_MS" orderer3.example.com >/dev/null 2>&1; sleep 4; }
stop_attack(){ docker rm -f pumba-l2 >/dev/null 2>&1 || true; }

# force N elections by restarting the current leader; count orderer3 wins
forced_election_test(){ # $1=label
  local wins=0 changes=0 prev=""
  echo "  [elect] $1: forcing $N_ELECT elections..." | tee -a "$OUT/summary.txt"
  for i in $(seq 1 "$N_ELECT"); do
    local L; L=$(leader_id); local LC; LC=$(name_for_id "$L"); [ -z "$LC" ] && LC=orderer.example.com
    docker restart "$LC" >/dev/null 2>&1; sleep 13
    local NL; NL=$(leader_id)
    [ "$NL" = "3" ] && wins=$((wins+1))
    [ -n "$NL" ] && [ "$NL" != "$prev" ] && changes=$((changes+1)); prev="$NL"
    echo "    election $i: restarted id=$L -> new leader id=$NL" | tee -a "$OUT/summary.txt"
  done
  echo "  [elect] $1 RESULT: orderer3 won $wins/$N_ELECT forced elections; $changes distinct leaders" | tee -a "$OUT/summary.txt"
  echo "$1,$wins,$N_ELECT,$changes" >> "$OUT/election_results.csv"
}

pin_leader_3(){ # only used in condition A (no suppression). 25 tries.
  echo "  [pin] forcing orderer3 to leader (cond A)..." | tee -a "$OUT/summary.txt"
  for i in $(seq 1 25); do
    local L; L=$(leader_id)
    [ "$L" = "3" ] && { echo "    -> orderer3 is LEADER (try $i)" | tee -a "$OUT/summary.txt"; return 0; }
    local LC; LC=$(name_for_id "$L"); [ -z "$LC" ] && LC=orderer.example.com
    docker restart "$LC" >/dev/null 2>&1; sleep 13
  done
  echo "    WARN: could not pin orderer3 after 25 tries" | tee -a "$OUT/summary.txt"; return 1
}

sweep(){ # $1=label
  local dir="$OUT/$1"; mkdir -p "$dir"
  local hb; hb=$(geth); local tb; tb=$(date +%s); local lb; lb=$(leader_id)
  docker rm -f caliper-l2 >/dev/null 2>&1 || true
  docker run --rm --name caliper-l2 --network fabric_test \
    -v "$WS:/hyperledger/caliper/workspace" -v "$CRYPTO:/cryptoMount" \
    --add-host=host.docker.internal:host-gateway \
    -e CALIPER_BIND_SUT=fabric:fabric-gateway \
    -e CALIPER_BENCHCONFIG=benchmarks/belowceiling-sweep.yaml \
    -e CALIPER_NETWORKCONFIG=networks/fabric-5node.yaml \
    -e CALIPER_FLOW_ONLY_TEST=true \
    -e CALIPER_REPORT_PATH=/hyperledger/caliper/workspace/report-$1.html \
    hyperledger/caliper:0.6.0 launch manager > "$dir/caliper.log" 2>&1
  cp "$WS/report-$1.html" "$dir/" 2>/dev/null || true
  local ha; ha=$(geth); local ta; ta=$(date +%s); local la; la=$(leader_id)
  echo ">>> sweep $1: ledger Δ=$((ha-hb)) blocks / $((ta-tb))s | leader start=$lb end=$la" | tee -a "$OUT/summary.txt"
  grep -aE "\| rate-[0-9]+" "$dir/caliper.log" 2>/dev/null | head -6 | sed 's/^/    /' | tee -a "$OUT/summary.txt"
}

# ============================ run ============================
echo "=== sidecar socket? ===" | tee "$OUT/summary.txt"
docker exec orderer.example.com sh -c 'test -S /var/run/raft-advisor.sock && echo SOCKET_OK || echo SOCKET_MISSING' | tee -a "$OUT/summary.txt"
echo "label,orderer3_wins,n_elections,distinct_leaders" > "$OUT/election_results.csv"

# start background refresher (blacklist=[] initially)
set_blacklist "[]"
refresher & REFRESH_PID=$!
echo "[refresher] started pid=$REFRESH_PID (bumps seq ~0.3s)" | tee -a "$OUT/summary.txt"

start_attack   # orderer3 +ATTACK_MS for the whole experiment

echo "######## CONDITION A: attack, NO BORA (blacklist=[]) ########" | tee -a "$OUT/summary.txt"
set_blacklist "[]"
forced_election_test "A_noBORA"
pin_leader_3
sweep "A_noBORA_slowleader"

echo "######## CONDITION B: attack + BORA (blacklist=[3], sustained) ########" | tee -a "$OUT/summary.txt"
set_blacklist "[3]"
forced_election_test "B_BORA"
sweep "B_BORA_healthyleader"

# teardown
set_blacklist "[]"
rm -f "$RUN_FLAG"; sleep 1; kill "$REFRESH_PID" 2>/dev/null || true
stop_attack
echo "LEADER_SCENARIO_V2_DONE (results: $OUT)" | tee -a "$OUT/summary.txt"
