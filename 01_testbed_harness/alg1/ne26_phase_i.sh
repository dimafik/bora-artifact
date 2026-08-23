#!/usr/bin/env bash
# Phase I: Caliper saturation under VERY STRONG 1000ms attack on orderer3.
# Tests whether BORA effect grows monotonically with attack severity.
set -e
RESULTS=/mnt/d/fabric-d2/results/ne26_phase_i_$(date +%Y%m%d-%H%M%S)
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
echo "NE26 Phase I — 1000ms attack saturation"
echo "Results: $RESULTS"
echo "==========================================="

# Sidecar v1 expected to be already running externally.

# I1: clean
echo
echo "--- I1: clean, B_t=[] ---"
mkdir -p "$RESULTS/phaseI1_clean"
write_advice "[]" 100000 "false"
for s in 1 2 3; do
  echo "  seed $s..."
  run_caliper "$s" "I1_clean" "$RESULTS/phaseI1_clean"
done

# I2: 1000ms attack no BORA
echo
echo "--- I2: 1000ms attack, B_t=[] ---"
mkdir -p "$RESULTS/phaseI2_attack_only"
docker run -d --name pumba-i2 -v /var/run/docker.sock:/var/run/docker.sock \
  gaiaadm/pumba:latest --interval 15m --log-level info \
  netem --tc-image gaiadocker/iproute2 --duration 12m \
  delay --time 1000 orderer3.example.com 2>&1 | tail -1
sleep 5
write_advice "[]" 110000 "false"
for s in 1 2 3; do
  echo "  seed $s..."
  run_caliper "$s" "I2_attack" "$RESULTS/phaseI2_attack_only"
done
docker rm -f pumba-i2 2>&1 | tail -1 || true

# I3: 1000ms attack BORA active
echo
echo "--- I3: 1000ms attack, B_t=[3] ---"
mkdir -p "$RESULTS/phaseI3_bora_active"
docker run -d --name pumba-i3 -v /var/run/docker.sock:/var/run/docker.sock \
  gaiaadm/pumba:latest --interval 15m --log-level info \
  netem --tc-image gaiadocker/iproute2 --duration 12m \
  delay --time 1000 orderer3.example.com 2>&1 | tail -1
sleep 5
write_advice "[3]" 120000 "false"
for s in 1 2 3; do
  echo "  seed $s..."
  run_caliper "$s" "I3_bora" "$RESULTS/phaseI3_bora_active"
done
docker rm -f pumba-i3 2>&1 | tail -1 || true
write_advice "[]" 130000 "false"

echo
echo "PHASE_I_OK"
echo "Results: $RESULTS"
