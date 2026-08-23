#!/usr/bin/env bash
# Wait for the orderer backlog to drain (ledger height stabilises under
# zero load), then run the corrected below-ceiling sweep (clean) and
# cross-check Caliper Succ against ledger block-height delta.
set -u
WORKSPACE=/mnt/d/fabric-d2/caliper-workspace
CRYPTO=/mnt/d/fabric-d2/fabric-samples/test-network/organizations
OUT=/mnt/d/fabric-d2/results/validate_$(date +%Y%m%d-%H%M%S)
mkdir -p "$OUT"

geth() { docker exec peer0.org1.example.com peer channel getinfo -c mychannel 2>/dev/null \
         | grep -ao '"height":[0-9]*' | grep -ao '[0-9]*'; }

echo "[validate] waiting for backlog to drain (height must stabilise)..."
prev=$(geth); stable=0; iters=0; MAXITERS=320   # 320*15s = 80 min cap
while [ $iters -lt $MAXITERS ]; do
  sleep 15
  cur=$(geth)
  d=$(( cur - prev ))
  echo "[validate] height=$cur (+$d in 15s)"
  if [ "$d" -le 5 ]; then stable=$((stable+1)); else stable=0; fi
  prev=$cur
  iters=$((iters+1))
  [ $stable -ge 2 ] && break   # two consecutive ~idle windows => drained
done
if [ $stable -lt 2 ]; then
  echo "[validate] BACKLOG NOT DRAINED after cap (height still climbing at $prev); skipping validation to avoid an inconclusive run."
  echo "VALIDATE_SKIPPED_BACKLOG height=$prev"
  exit 0
fi
echo "[validate] backlog drained at height=$prev. Starting validation sweep."

H_BEFORE=$(geth)
T_BEFORE=$(date +%s)

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
H_AFTER=$(geth)
T_AFTER=$(date +%s)

DH=$(( H_AFTER - H_BEFORE ))
DT=$(( T_AFTER - T_BEFORE ))
echo "=================== VALIDATION RESULT ==================="
echo "ledger height: $H_BEFORE -> $H_AFTER  (Δ=$DH blocks over ${DT}s incl. setup)"
echo "--- Caliper per-round Succ/Fail (live observer tail) ---"
grep -aoiE "rate-[0-9]+ Round [0-9]+ Transaction Info\] - Submitted: [0-9]+ Succ: [0-9]+ Fail:[0-9]+" "$OUT/caliper-validate.log" 2>/dev/null \
  | awk -F'[][]' '{print $0}' | tail -20
echo "--- Caliper final summary table (Succ/Throughput) ---"
grep -aE "\| rate-[0-9]+" "$OUT/caliper-validate.log" 2>/dev/null | head -20
echo "Results dir: $OUT"
echo "VALIDATE_DONE"
