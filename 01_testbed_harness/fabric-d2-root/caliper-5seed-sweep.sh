#!/bin/bash
# Run Caliper sweep 5 seeds × 4 rates, archive each report
set -e

WORKSPACE=/mnt/d/fabric-d2/caliper-workspace
CRYPTO=/mnt/d/fabric-d2/fabric-samples/test-network/organizations
ARCHIVE=/mnt/d/fabric-d2/results/archive/5node_caliper_2026-06-07
mkdir -p "$ARCHIVE"

for seed in 1 2 3 4 5; do
  echo ""
  echo "######################################"
  echo "######## SEED $seed ##################"
  echo "######################################"
  docker rm -f caliper-d2 2>&1 | tail -1 || true

  # Each seed gets its own report.html
  REPORT="report-seed${seed}.html"
  LOG="caliper-seed${seed}.log"

  docker run --rm \
    --name caliper-d2 \
    --network fabric_test \
    -v "$WORKSPACE:/hyperledger/caliper/workspace" \
    -v "$CRYPTO:/cryptoMount" \
    --add-host=host.docker.internal:host-gateway \
    -e CALIPER_BIND_SUT=fabric:fabric-gateway \
    -e CALIPER_BENCHCONFIG=benchmarks/createasset-sweep.yaml \
    -e CALIPER_NETWORKCONFIG=networks/fabric-5node.yaml \
    -e CALIPER_FLOW_ONLY_TEST=true \
    -e CALIPER_REPORT_PATH=/hyperledger/caliper/workspace/$REPORT \
    hyperledger/caliper:0.6.0 launch manager > "$WORKSPACE/$LOG" 2>&1

  # Archive
  cp "$WORKSPACE/$REPORT" "$ARCHIVE/$REPORT"
  cp "$WORKSPACE/$LOG" "$ARCHIVE/$LOG"
  echo "=== SEED $seed COMPLETE ==="
  grep -E "Finished round|All test results|throughput" "$WORKSPACE/$LOG" | head -10
done

echo ""
echo "All seeds completed. Archive: $ARCHIVE"
ls -la "$ARCHIVE"
