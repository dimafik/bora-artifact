#!/usr/bin/env bash
# Corrected NE26 campaign at SUB-CEILING rates (100-500 tps, below the
# ~570 tps commit ceiling) so Caliper confirms commits (Succ>0). Three
# conditions per seed: clean / attack(+500ms orderer3) / BORA(blacklist 3).
# Records per-rate Caliper Succ+Throughput AND ledger block-height delta.
# Requires: BORA-patched orderers + bora-sidecar already deployed.
set -u
SEEDS="${SEEDS:-1}"
ATTACK_MS="${ATTACK_MS:-500}"
WS=/mnt/d/fabric-d2/caliper-workspace
CRYPTO=/mnt/d/fabric-d2/fabric-samples/test-network/organizations
OUT=/mnt/d/fabric-d2/results/corrected_$(date +%Y%m%d-%H%M%S); mkdir -p "$OUT"
ORDERERS=(orderer.example.com orderer2.example.com orderer3.example.com orderer4.example.com orderer5.example.com)
SEQ=1000

geth(){ docker exec peer0.org1.example.com peer channel getinfo -c mychannel 2>/dev/null | grep -ao '"height":[0-9]*' | grep -ao '[0-9]*'; }
leader(){ docker logs --tail 80 orderer.example.com 2>&1 | grep -aoiE "leader changed.*to [0-9]+|became leader|raft.node: [0-9]+ became leader" | tail -1; }
write_advice(){ # $1=blacklist json
  SEQ=$((SEQ+1))
  for o in "${ORDERERS[@]}"; do
    docker exec "$o" sh -c "echo '{\"blacklist\":$1,\"seq\":$SEQ,\"fail_open\":false}' > /tmp/bora-advice.json"
  done
}
start_attack(){ docker rm -f pumba-c >/dev/null 2>&1 || true
  docker run -d --name pumba-c -v /var/run/docker.sock:/var/run/docker.sock gaiaadm/pumba:latest \
    --interval 20m --log-level warning netem --tc-image gaiadocker/iproute2 --duration 18m \
    delay --time "$ATTACK_MS" orderer3.example.com >/dev/null 2>&1; sleep 5; }
stop_attack(){ docker rm -f pumba-c >/dev/null 2>&1 || true; }

run_one(){ # $1=label dir, $2=seed
  local dir="$OUT/$1"; mkdir -p "$dir"
  local hb=$(geth); local tb=$(date +%s)
  docker rm -f caliper-c >/dev/null 2>&1 || true
  docker run --rm --name caliper-c --network fabric_test \
    -v "$WS:/hyperledger/caliper/workspace" -v "$CRYPTO:/cryptoMount" \
    --add-host=host.docker.internal:host-gateway \
    -e CALIPER_BIND_SUT=fabric:fabric-gateway \
    -e CALIPER_BENCHCONFIG=benchmarks/belowceiling-sweep.yaml \
    -e CALIPER_NETWORKCONFIG=networks/fabric-5node.yaml \
    -e CALIPER_FLOW_ONLY_TEST=true \
    -e CALIPER_REPORT_PATH=/hyperledger/caliper/workspace/report-$1-s$2.html \
    hyperledger/caliper:0.6.0 launch manager > "$dir/caliper-s$2.log" 2>&1
  cp "$WS/report-$1-s$2.html" "$dir/" 2>/dev/null || true
  local ha=$(geth); local ta=$(date +%s)
  echo ">>> $1 seed$2: ledger Δ=$((ha-hb)) blocks / $((ta-tb))s | leader=$(leader)" | tee -a "$OUT/summary.txt"
  grep -aE "\| rate-[0-9]+" "$dir/caliper-s$2.log" 2>/dev/null | head -5 | sed "s/^/    /" | tee -a "$OUT/summary.txt"
}

echo "=== sanity: sidecar socket up on orderer1? ===" | tee "$OUT/summary.txt"
docker exec orderer.example.com sh -c 'test -S /var/run/raft-advisor.sock && echo SOCKET_OK || echo SOCKET_MISSING' | tee -a "$OUT/summary.txt"

for s in $(seq 1 "$SEEDS"); do
  echo "######## SEED $s ########" | tee -a "$OUT/summary.txt"
  echo "--- clean ---" | tee -a "$OUT/summary.txt"
  write_advice "[]"; stop_attack; run_one "clean" "$s"
  echo "--- attack (+${ATTACK_MS}ms orderer3, no BORA) ---" | tee -a "$OUT/summary.txt"
  write_advice "[]"; start_attack; run_one "attack" "$s"; stop_attack
  echo "--- BORA (+${ATTACK_MS}ms orderer3, blacklist 3) ---" | tee -a "$OUT/summary.txt"
  start_attack; write_advice "[3]"; run_one "bora" "$s"; stop_attack; write_advice "[]"
done

echo "CORRECTED_CAMPAIGN_DONE  (results: $OUT)" | tee -a "$OUT/summary.txt"
