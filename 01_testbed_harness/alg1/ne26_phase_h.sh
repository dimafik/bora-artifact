#!/usr/bin/env bash
# NE26 Phase H: Caliper saturation + 500ms strong attack.
# Closes the matrix:
#   200ms low-load = Phase E
#   200ms saturation = Phase F
#   500ms low-load = Phase G
#   500ms saturation = Phase H  <-- this run
set -e
RESULTS=/mnt/d/fabric-d2/results/ne26_phase_h_$(date +%Y%m%d-%H%M%S)
mkdir -p "$RESULTS"
WORKSPACE=/mnt/d/fabric-d2/caliper-workspace
CRYPTO=/mnt/d/fabric-d2/fabric-samples/test-network/organizations
ORDERERS=(orderer.example.com orderer2.example.com orderer3.example.com orderer4.example.com orderer5.example.com)

write_advice () {
  local payload="{\"blacklist\":$1,\"seq\":$2,\"fail_open\":$3}"
  for o in "${ORDERERS[@]}"; do
    docker exec "$o" sh -c "echo '$payload' > /tmp/bora-advice.json"
  done
}

run_caliper () {
  docker rm -f caliper-d2 2>&1 | tail -1 || true
  docker run --rm \
    --name caliper-d2 \
    --network fabric_test \
    -v "$WORKSPACE:/hyperledger/caliper/workspace" \
    -v "$CRYPTO:/cryptoMount" \
    --add-host=host.docker.internal:host-gateway \
    -e CALIPER_BIND_SUT=fabric:fabric-gateway \
    -e CALIPER_BENCHCONFIG=benchmarks/saturation-refine.yaml \
    -e CALIPER_NETWORKCONFIG=networks/fabric-5node.yaml \
    -e CALIPER_FLOW_ONLY_TEST=true \
    -e CALIPER_REPORT_PATH=/hyperledger/caliper/workspace/report-$2-seed${1}.html \
    hyperledger/caliper:0.6.0 launch manager > "$3/caliper-$2-seed${1}.log" 2>&1
  cp "$WORKSPACE/report-$2-seed${1}.html" "$3/" 2>/dev/null || true
}

echo "==========================================="
echo "NE26 Phase H — Caliper + 500ms strong attack"
echo "Results: $RESULTS"
echo "==========================================="

# H1: clean baseline
echo
echo "--- H1: clean, B_t=[] ---"
mkdir -p "$RESULTS/phaseH1_clean"
write_advice "[]" 50000 "false"
for s in 1 2 3; do
  echo "  seed $s..."
  run_caliper "$s" "H1_clean" "$RESULTS/phaseH1_clean"
done

# H2: 500ms attack, no BORA
echo
echo "--- H2: 500ms attack, B_t=[] ---"
mkdir -p "$RESULTS/phaseH2_attack_only"
docker run -d --name pumba-h2 -v /var/run/docker.sock:/var/run/docker.sock \
  gaiaadm/pumba:latest --interval 15m --log-level info \
  netem --tc-image gaiadocker/iproute2 --duration 12m \
  delay --time 500 orderer3.example.com 2>&1 | tail -1
sleep 5
write_advice "[]" 60000 "false"
for s in 1 2 3; do
  echo "  seed $s..."
  run_caliper "$s" "H2_attack" "$RESULTS/phaseH2_attack_only"
done
docker rm -f pumba-h2 2>&1 | tail -1 || true

# H3: 500ms attack, BORA active
echo
echo "--- H3: 500ms attack, B_t=[3] ---"
mkdir -p "$RESULTS/phaseH3_bora_active"
docker run -d --name pumba-h3 -v /var/run/docker.sock:/var/run/docker.sock \
  gaiaadm/pumba:latest --interval 15m --log-level info \
  netem --tc-image gaiadocker/iproute2 --duration 12m \
  delay --time 500 orderer3.example.com 2>&1 | tail -1
sleep 5
write_advice "[3]" 70000 "false"
for s in 1 2 3; do
  echo "  seed $s..."
  run_caliper "$s" "H3_bora" "$RESULTS/phaseH3_bora_active"
done
docker rm -f pumba-h3 2>&1 | tail -1 || true
write_advice "[]" 80000 "false"

echo
echo "PHASE_H_OK"
echo "Results: $RESULTS"
