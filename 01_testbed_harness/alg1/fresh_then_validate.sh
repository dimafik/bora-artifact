#!/usr/bin/env bash
# Tear down the backlog-polluted network, bring up a FRESH clean 5-orderer
# cluster, then run the corrected below-ceiling sweep and cross-check
# Caliper Succ against ledger block-height delta. Proves the Succ=0 issue
# was oversubscription, not a consensus/pipeline failure.
set -u
WORKSPACE=/mnt/d/fabric-d2/caliper-workspace
CRYPTO=/mnt/d/fabric-d2/fabric-samples/test-network/organizations
OUT=/mnt/d/fabric-d2/results/validate_fresh_$(date +%Y%m%d-%H%M%S)
mkdir -p "$OUT"

echo "================ STEP 1: fresh network ================"
bash /mnt/d/fabric-d2/fresh-network.sh 2>&1 | tee "$OUT/fresh-network.log"
if ! grep -q "Fresh network ready" "$OUT/fresh-network.log"; then
  echo "FRESH_NETWORK_FAILED — see $OUT/fresh-network.log"
  tail -15 "$OUT/fresh-network.log"
  exit 1
fi
echo "[fresh] network ready; letting leaders settle..."
sleep 15

geth() { docker exec peer0.org1.example.com peer channel getinfo -c mychannel 2>/dev/null \
         | grep -ao '"height":[0-9]*' | grep -ao '[0-9]*'; }
echo "[fresh] clean ledger height = $(geth)  (should be small, ~2-3)"

echo "================ STEP 2: below-ceiling sweep (100-500 tps) ================"
H_BEFORE=$(geth); T_BEFORE=$(date +%s)
docker rm -f caliper-validate 2>/dev/null || true
docker run --rm --name caliper-validate \
  --network fabric_test \
  -v "$WORKSPACE:/hyperledger/caliper/workspace" \
  -v "$CRYPTO:/cryptoMount" \
  --add-host=host.docker.internal:host-gateway \
  -e CALIPER_BIND_SUT=fabric:fabric-gateway \
  -e CALIPER_BENCHCONFIG=benchmarks/belowceiling-sweep.yaml \
  -e CALIPER_NETWORKCONFIG=networks/fabric-5node.yaml \
  -e CALIPER_FLOW_ONLY_TEST=true \
  -e CALIPER_REPORT_PATH=/hyperledger/caliper/workspace/report-validate.html \
  hyperledger/caliper:0.6.0 launch manager > "$OUT/caliper-validate.log" 2>&1
cp "$WORKSPACE/report-validate.html" "$OUT/" 2>/dev/null || true
H_AFTER=$(geth); T_AFTER=$(date +%s)

echo "================ RESULT ================"
DH=$(( H_AFTER - H_BEFORE )); DT=$(( T_AFTER - T_BEFORE ))
echo "ledger height: $H_BEFORE -> $H_AFTER  (Δ=$DH blocks over ${DT}s incl. setup; ~$(( DH>0 ? DH*10/DT : 0 )) tx/s avg)"
echo "--- Caliper live observer (last Succ/Fail per round) ---"
grep -aoiE "rate-[0-9]+ Round [0-9]+ Transaction Info\] - Submitted: [0-9]+ Succ: [0-9]+ Fail:[0-9]+" "$OUT/caliper-validate.log" 2>/dev/null | tail -10
echo "--- Caliper final summary (Succ | Send Rate | Throughput) ---"
grep -aE "\| rate-[0-9]+" "$OUT/caliper-validate.log" 2>/dev/null | head -10
echo "Results dir: $OUT"
echo "FRESH_VALIDATE_DONE"
