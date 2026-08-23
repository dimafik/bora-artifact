#!/bin/bash
set -e
cd /mnt/d/fabric-d2/fabric-samples/test-network
export PATH=/tmp/bin:/mnt/d/fabric-d2/fabric-samples/bin-linux/bin:/usr/local/bin:/usr/bin:/bin

echo "=== STEP 1 Tear down ==="
DOCKER_SOCK=/var/run/docker.sock docker compose -f compose/compose-test-net.yaml -f compose/docker/docker-compose-test-net.yaml down --volumes 2>&1 | tail -3 || true
docker network rm fabric_test 2>/dev/null || true

echo "=== STEP 2 Cryptogen ==="
rm -rf organizations/ordererOrganizations organizations/peerOrganizations channel-artifacts system-genesis-block
mkdir -p channel-artifacts system-genesis-block
cryptogen generate --config=./organizations/cryptogen/crypto-config-orderer.yaml --output=organizations
cryptogen generate --config=./organizations/cryptogen/crypto-config-org1.yaml --output=organizations
cryptogen generate --config=./organizations/cryptogen/crypto-config-org2.yaml --output=organizations
echo "Orderer TLS:"
ls organizations/ordererOrganizations/example.com/orderers/orderer.example.com/tls/

echo "=== STEP 3 Genesis ==="
export FABRIC_CFG_PATH=/mnt/d/fabric-d2/fabric-samples/test-network/configtx
configtxgen -profile ChannelUsingRaft -outputBlock ./channel-artifacts/mychannel.block -channelID mychannel 2>&1 | tail -3
ls -la channel-artifacts/

echo "=== STEP 4 Start containers ==="
export FABRIC_CFG_PATH=/mnt/d/fabric-d2/fabric-samples/config
DOCKER_SOCK=/var/run/docker.sock COMPOSE_PROJECT_NAME=fabric docker compose -f compose/compose-test-net.yaml -f compose/docker/docker-compose-test-net.yaml up -d 2>&1 | tail -10
sleep 10
docker ps --filter 'name=orderer' --filter 'name=peer0' --format 'table {{.Names}}\t{{.Status}}'

echo "=== STEP 5 osnadmin join channel ==="
ORDERER_CA=organizations/ordererOrganizations/example.com/orderers/orderer.example.com/msp/tlscacerts/tlsca.example.com-cert.pem
ORDERER_CERT=organizations/ordererOrganizations/example.com/orderers/orderer.example.com/tls/server.crt
ORDERER_KEY=organizations/ordererOrganizations/example.com/orderers/orderer.example.com/tls/server.key
osnadmin channel join --channelID mychannel --config-block ./channel-artifacts/mychannel.block -o localhost:7053 --ca-file "$ORDERER_CA" --client-cert "$ORDERER_CERT" --client-key "$ORDERER_KEY" 2>&1 | tail -5

echo "=== STEP 6 Verify channel ==="
osnadmin channel list -o localhost:7053 --ca-file "$ORDERER_CA" --client-cert "$ORDERER_CERT" --client-key "$ORDERER_KEY" 2>&1 | tail -10
