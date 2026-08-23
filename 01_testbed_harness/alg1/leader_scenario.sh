#!/usr/bin/env bash
# BORA value scenario: make orderer3 the LEADER, then attack it. A slow
# leader throttles throughput. BORA(blacklist 3) should let orderer3 lose
# leadership to a healthy node and prevent it re-winning -> throughput
# recovers. Uses a large delay so the slow leader actually destabilises
# (must exceed the election timeout for BORA's election-suppression to bite).
set -u
ATTACK_MS="${ATTACK_MS:-2000}"
WS=/mnt/d/fabric-d2/caliper-workspace
CRYPTO=/mnt/d/fabric-d2/fabric-samples/test-network/organizations
OUT=/mnt/d/fabric-d2/results/leaderscn_$(date +%Y%m%d-%H%M%S); mkdir -p "$OUT"
ORDERERS=(orderer.example.com orderer2.example.com orderer3.example.com orderer4.example.com orderer5.example.com)
SEQ=2000
name_for_id(){ case $1 in 1) echo orderer.example.com;; 2) echo orderer2.example.com;; 3) echo orderer3.example.com;; 4) echo orderer4.example.com;; 5) echo orderer5.example.com;; *) echo "";; esac; }
leader_id(){ docker logs --tail 400 orderer.example.com 2>&1 | grep -ao "Raft leader changed:[^c]*-> [0-9][0-9]*" | tail -1 | grep -ao "[0-9][0-9]*$"; }
geth(){ docker exec peer0.org1.example.com peer channel getinfo -c mychannel 2>/dev/null | grep -ao '"height":[0-9]*' | grep -ao '[0-9]*'; }
write_advice(){ SEQ=$((SEQ+1)); for o in "${ORDERERS[@]}"; do docker exec "$o" sh -c "echo '{\"blacklist\":$1,\"seq\":$SEQ,\"fail_open\":false}' > /tmp/bora-advice.json"; done; }
start_attack(){ docker rm -f pumba-l >/dev/null 2>&1 || true
  docker run -d --name pumba-l -v /var/run/docker.sock:/var/run/docker.sock gaiaadm/pumba:latest \
    --interval 30m --log-level warning netem --tc-image gaiadocker/iproute2 --duration 25m \
    delay --time "$ATTACK_MS" orderer3.example.com >/dev/null 2>&1; sleep 4; }
stop_attack(){ docker rm -f pumba-l >/dev/null 2>&1 || true; }

pin_leader_3(){
  echo "[pin] forcing orderer3 to leader..." | tee -a "$OUT/summary.txt"
  for i in $(seq 1 14); do
    L=$(leader_id)
    echo "  attempt $i: current leader id=$L" | tee -a "$OUT/summary.txt"
    [ "$L" = "3" ] && { echo "  -> orderer3 is LEADER" | tee -a "$OUT/summary.txt"; return 0; }
    LC=$(name_for_id "$L"); [ -z "$LC" ] && LC=orderer.example.com
    docker restart "$LC" >/dev/null 2>&1; sleep 14
  done
  echo "  WARN: could not pin orderer3 as leader after 14 tries" | tee -a "$OUT/summary.txt"; return 1
}

run_one(){ # $1 label
  local dir="$OUT/$1"; mkdir -p "$dir"
  local hb=$(geth); local tb=$(date +%s); local lb=$(leader_id)
  docker rm -f caliper-l >/dev/null 2>&1 || true
  docker run --rm --name caliper-l --network fabric_test \
    -v "$WS:/hyperledger/caliper/workspace" -v "$CRYPTO:/cryptoMount" \
    --add-host=host.docker.internal:host-gateway \
    -e CALIPER_BIND_SUT=fabric:fabric-gateway \
    -e CALIPER_BENCHCONFIG=benchmarks/belowceiling-sweep.yaml \
    -e CALIPER_NETWORKCONFIG=networks/fabric-5node.yaml \
    -e CALIPER_FLOW_ONLY_TEST=true \
    -e CALIPER_REPORT_PATH=/hyperledger/caliper/workspace/report-$1.html \
    hyperledger/caliper:0.6.0 launch manager > "$dir/caliper.log" 2>&1
  cp "$WS/report-$1.html" "$dir/" 2>/dev/null || true
  local ha=$(geth); local ta=$(date +%s); local la=$(leader_id)
  echo ">>> $1: ledger Δ=$((ha-hb)) / $((ta-tb))s | leader start=$lb end=$la | leaderchanges during run:" | tee -a "$OUT/summary.txt"
  docker logs --since "$((ta-tb+10))s" orderer.example.com 2>&1 | grep -ao "Raft leader changed:[^c]*-> [0-9]*" | sed 's/^/      /' | tee -a "$OUT/summary.txt"
  grep -aE "\| rate-[0-9]+" "$dir/caliper.log" 2>/dev/null | head -5 | sed 's/^/    /' | tee -a "$OUT/summary.txt"
}

echo "=== sidecar socket? ===" | tee "$OUT/summary.txt"
docker exec orderer.example.com sh -c 'test -S /var/run/raft-advisor.sock && echo OK || echo MISSING' | tee -a "$OUT/summary.txt"

echo "######## ATTACK-LEADER (orderer3 leader, +${ATTACK_MS}ms, no BORA) ########" | tee -a "$OUT/summary.txt"
write_advice "[]"; stop_attack; pin_leader_3; start_attack; run_one "attack_leader"; stop_attack

echo "######## BORA-LEADER (orderer3 leader, +${ATTACK_MS}ms, blacklist 3) ########" | tee -a "$OUT/summary.txt"
stop_attack; pin_leader_3; start_attack; write_advice "[3]"; run_one "bora_leader"; stop_attack; write_advice "[]"

echo "LEADER_SCENARIO_DONE (results: $OUT)" | tee -a "$OUT/summary.txt"
