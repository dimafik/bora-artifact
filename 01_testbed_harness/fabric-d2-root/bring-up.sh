#!/bin/bash
set -e
cd /mnt/d/fabric-d2/fabric-samples/test-network
export PATH="/mnt/d/fabric-d2/fabric-samples/bin-linux/bin:/usr/local/bin:/usr/bin:/bin"
export FABRIC_CFG_PATH="/mnt/d/fabric-d2/fabric-samples/config"

echo "=== STEP 1: Down (cleanup) ==="
./network.sh down 2>&1 | tail -3 || true

echo "=== STEP 2: Up ==="
./network.sh up 2>&1 | tail -15

echo "=== STEP 3: createChannel mychannel ==="
./network.sh createChannel -c mychannel 2>&1 | tail -10

echo "=== STEP 4: containers ==="
docker ps --filter "name=org\|orderer" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
