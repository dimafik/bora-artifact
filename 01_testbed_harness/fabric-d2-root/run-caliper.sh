#!/bin/bash
# Run Caliper Docker against running 5-orderer Fabric network
set -e

WORKSPACE=/mnt/d/fabric-d2/caliper-workspace
CRYPTO=/mnt/d/fabric-d2/fabric-samples/test-network/organizations

# Caliper Docker run
# - mount workspace (configs + workload)
# - mount crypto for cert/key paths
# - join fabric_test network so it can resolve peer/orderer hostnames
# - use host.docker.internal for localhost
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
  -e CALIPER_REPORT_PATH=/hyperledger/caliper/workspace/report.html \
  hyperledger/caliper:0.6.0 launch manager 2>&1
