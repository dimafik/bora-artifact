#!/usr/bin/env bash
# Dry-run validate the generated N-node configtx genesis (non-destructive).
set -u
N="${1:-7}"
cd /mnt/d/fabric-d2/fabric-samples/test-network
export PATH="/mnt/d/fabric-d2/fabric-samples/bin-linux/bin:/tmp/bin:/usr/local/bin:/usr/bin:/bin"
export FABRIC_CFG_PATH="$PWD/configtx"
cp configtx/configtx.yaml /tmp/configtx.bak 2>/dev/null || true
cp "configtx/configtx-${N}node.yaml" configtx/configtx.yaml
rm -f "/tmp/test${N}.block"
configtxgen -profile ChannelUsingRaft -outputBlock "/tmp/test${N}.block" -channelID mychannel 2>&1 | tail -6
cp /tmp/configtx.bak configtx/configtx.yaml 2>/dev/null || true
if [ -f "/tmp/test${N}.block" ]; then echo "GENESIS_${N}_OK ($(stat -c%s /tmp/test${N}.block) bytes)"; else echo "GENESIS_${N}_FAIL"; fi
# also validate compose syntax
DOCKER_SOCK=/var/run/docker.sock docker compose -f "${N}node-raft.yaml" config -q 2>&1 | tail -4 && echo "COMPOSE_${N}_OK" || echo "COMPOSE_${N}_FAIL"
