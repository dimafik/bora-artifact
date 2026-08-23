#!/usr/bin/env bash
# Phase J: simultaneous 300ms attack on orderer3 AND orderer4.
# Tests BORA's cap |B_t| < f = 2 boundary: blacklist one attacker,
# the other still drags the cluster.
#
# Sub-phases:
#  J1 clean
#  J2 both attacked, B_t = []
#  J3 both attacked, B_t = [3]  (blacklist orderer3 only; can't blacklist 4 due to cap)
set -e
RESULTS=/mnt/d/fabric-d2/results/ne26_phase_j_$(date +%Y%m%d-%H%M%S)
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

start_dual_attack () {
  local delay=$1
  docker run -d --name "pumba-j-3" -v /var/run/docker.sock:/var/run/docker.sock \
    gaiaadm/pumba:latest --interval 15m --log-level info \
    netem --tc-image gaiadocker/iproute2 --duration 12m \
    delay --time "$delay" orderer3.example.com > /dev/null 2>&1
  docker run -d --name "pumba-j-4" -v /var/run/docker.sock:/var/run/docker.sock \
    gaiaadm/pumba:latest --interval 15m --log-level info \
    netem --tc-image gaiadocker/iproute2 --duration 12m \
    delay --time "$delay" orderer4.example.com > /dev/null 2>&1
}
stop_dual_attack () {
  docker rm -f pumba-j-3 pumba-j-4 2>&1 | tail -2 || true
}

echo "==========================================="
echo "NE26 Phase J — dual 300ms attack (orderer3 + orderer4)"
echo "Results: $RESULTS"
echo "==========================================="

# J1 clean
echo
echo "--- J1: clean, B_t=[] ---"
mkdir -p "$RESULTS/phaseJ1_clean"
write_advice "[]" 200000 "false"
for s in 1 2 3; do
  echo "  seed $s..."
  run_caliper "$s" "J1_clean" "$RESULTS/phaseJ1_clean"
done

# J2 dual attack no BORA
echo
echo "--- J2: dual 300ms attack, B_t=[] ---"
mkdir -p "$RESULTS/phaseJ2_attack_only"
start_dual_attack 300
sleep 5
write_advice "[]" 210000 "false"
for s in 1 2 3; do
  echo "  seed $s..."
  run_caliper "$s" "J2_attack" "$RESULTS/phaseJ2_attack_only"
done
stop_dual_attack

# J3 dual attack, BORA blacklists orderer3
echo
echo "--- J3: dual attack, B_t=[3] (cap limits to one) ---"
mkdir -p "$RESULTS/phaseJ3_bora_active"
start_dual_attack 300
sleep 5
write_advice "[3]" 220000 "false"
for s in 1 2 3; do
  echo "  seed $s..."
  run_caliper "$s" "J3_bora" "$RESULTS/phaseJ3_bora_active"
done
stop_dual_attack
write_advice "[]" 230000 "false"

echo
echo "PHASE_J_OK"
echo "Results: $RESULTS"
