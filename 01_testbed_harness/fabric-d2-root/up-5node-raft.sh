#!/bin/bash
# Bring up 5-orderer Raft Hyperledger Fabric test network from scratch
set -e
cd /mnt/d/fabric-d2/fabric-samples/test-network
export PATH=/tmp/bin:/tmp/go-install/go/bin:/mnt/d/fabric-d2/fabric-samples/bin-linux/bin:/usr/local/bin:/usr/bin:/bin

echo "=== STEP 0 Tear down any existing network ==="
DOCKER_SOCK=/var/run/docker.sock docker compose \
  -f 5node-raft.yaml down --volumes 2>&1 | tail -3 || true
DOCKER_SOCK=/var/run/docker.sock docker compose \
  -f compose/compose-test-net.yaml -f compose/docker/docker-compose-test-net.yaml down --volumes 2>&1 | tail -3 || true
docker network rm fabric_test 2>/dev/null || true

echo "=== STEP 1 Wipe orgs ==="
rm -rf organizations/ordererOrganizations organizations/peerOrganizations channel-artifacts system-genesis-block
mkdir -p channel-artifacts

echo "=== STEP 2 Cryptogen for 5 orderers + 2 peer orgs ==="
cryptogen generate \
  --config=./organizations/cryptogen/crypto-config-orderer-5node.yaml \
  --output=organizations 2>&1 | tail -3
cryptogen generate \
  --config=./organizations/cryptogen/crypto-config-org1.yaml \
  --output=organizations 2>&1 | tail -3
cryptogen generate \
  --config=./organizations/cryptogen/crypto-config-org2.yaml \
  --output=organizations 2>&1 | tail -3

echo "Generated orderer hosts:"
ls organizations/ordererOrganizations/example.com/orderers/

echo "=== STEP 3 Genesis block from 5-orderer configtx ==="
export FABRIC_CFG_PATH=/mnt/d/fabric-d2/fabric-samples/test-network/configtx
configtxgen -profile ChannelUsingRaft \
  -outputBlock ./channel-artifacts/mychannel.block \
  -channelID mychannel \
  -configPath ./configtx 2>&1 | tail -3

# Use configtx-5node.yaml as primary
cp configtx/configtx.yaml configtx/configtx.yaml.bak
cp configtx/configtx-5node.yaml configtx/configtx.yaml
configtxgen -profile ChannelUsingRaft \
  -outputBlock ./channel-artifacts/mychannel.block \
  -channelID mychannel 2>&1 | tail -5
cp configtx/configtx.yaml.bak configtx/configtx.yaml
rm configtx/configtx.yaml.bak
ls -la channel-artifacts/

echo "=== STEP 4 Start 5 orderers + 2 peers ==="
export FABRIC_CFG_PATH=/mnt/d/fabric-d2/fabric-samples/config
DOCKER_SOCK=/var/run/docker.sock COMPOSE_PROJECT_NAME=fabric \
  docker compose -f 5node-raft.yaml up -d 2>&1 | tail -10
sleep 10

echo "=== STEP 5 Container status ==="
docker ps --filter 'name=orderer' --filter 'name=peer0' --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
