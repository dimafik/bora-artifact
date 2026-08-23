#!/bin/bash
# Fully tear down + bring up fresh 5-orderer Raft + deploy basic chaincode with OR endorsement
# Used between Caliper seeds to avoid cumulative state-DB growth
set -e
cd /mnt/d/fabric-d2/fabric-samples/test-network
export PATH=/home/jinu337/go-install/bin:/mnt/d/fabric-d2/fabric-samples/bin-linux/bin:/usr/local/bin:/usr/bin:/bin

echo "  [step] Tearing down all Fabric containers and volumes..."
docker stop $(docker ps --filter 'name=orderer' --filter 'name=peer0' --filter 'name=dev-peer' -q) 2>/dev/null || true
docker rm -f $(docker ps -a --filter 'name=orderer' --filter 'name=peer0' --filter 'name=dev-peer' -q) 2>/dev/null || true
docker volume ls --filter name=fabric -q | xargs -r docker volume rm 2>/dev/null || true
docker volume ls --filter name=test-network -q | xargs -r docker volume rm 2>/dev/null || true
docker volume ls --filter name=compose -q | xargs -r docker volume rm 2>/dev/null || true
docker network rm fabric_test 2>/dev/null || true

echo "  [step] Wiping organizations and artifacts..."
rm -rf organizations/ordererOrganizations organizations/peerOrganizations channel-artifacts system-genesis-block
mkdir -p channel-artifacts

echo "  [step] Cryptogen for 5 orderers + 2 peer orgs..."
cryptogen generate --config=./organizations/cryptogen/crypto-config-orderer-5node.yaml --output=organizations 2>&1 | tail -2
cryptogen generate --config=./organizations/cryptogen/crypto-config-org1.yaml --output=organizations 2>&1 | tail -2
cryptogen generate --config=./organizations/cryptogen/crypto-config-org2.yaml --output=organizations 2>&1 | tail -2

echo "  [step] Genesis block from 5-node configtx..."
cp configtx/configtx.yaml configtx/configtx.yaml.bak
cp configtx/configtx-5node.yaml configtx/configtx.yaml
export FABRIC_CFG_PATH=/mnt/d/fabric-d2/fabric-samples/test-network/configtx
configtxgen -profile ChannelUsingRaft -outputBlock ./channel-artifacts/mychannel.block -channelID mychannel 2>&1 | tail -2
cp configtx/configtx.yaml.bak configtx/configtx.yaml
rm configtx/configtx.yaml.bak

echo "  [step] Starting 5 orderers + 2 peers..."
export FABRIC_CFG_PATH=/mnt/d/fabric-d2/fabric-samples/config
DOCKER_SOCK=/var/run/docker.sock COMPOSE_PROJECT_NAME=fabric \
  docker compose -f 5node-raft.yaml up -d 2>&1 | tail -3
sleep 8

echo "  [step] osnadmin join channel on all 5 orderers..."
ORDERER_CA=organizations/ordererOrganizations/example.com/orderers/orderer.example.com/msp/tlscacerts/tlsca.example.com-cert.pem
for n in 1 2 3 4 5; do
  case $n in
    1) ADM=7053  ; HOST=orderer  ;;
    2) ADM=8053  ; HOST=orderer2 ;;
    3) ADM=10053 ; HOST=orderer3 ;;
    4) ADM=11053 ; HOST=orderer4 ;;
    5) ADM=12053 ; HOST=orderer5 ;;
  esac
  CERT=organizations/ordererOrganizations/example.com/orderers/${HOST}.example.com/tls/server.crt
  KEY=organizations/ordererOrganizations/example.com/orderers/${HOST}.example.com/tls/server.key
  osnadmin channel join --channelID mychannel --config-block ./channel-artifacts/mychannel.block \
    -o localhost:$ADM --ca-file "$ORDERER_CA" --client-cert "$CERT" --client-key "$KEY" 2>&1 | grep -E 'consensusRelation|status' | head -2
done

echo "  [step] Peer Org1 + Org2 channel join..."
export CORE_PEER_TLS_ENABLED=true
TESTNET=/mnt/d/fabric-d2/fabric-samples/test-network
export CORE_PEER_LOCALMSPID=Org1MSP
export CORE_PEER_TLS_ROOTCERT_FILE=$TESTNET/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt
export CORE_PEER_MSPCONFIGPATH=$TESTNET/organizations/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp
export CORE_PEER_ADDRESS=localhost:7051
peer channel join -b ./channel-artifacts/mychannel.block 2>&1 | tail -1
export CORE_PEER_LOCALMSPID=Org2MSP
export CORE_PEER_TLS_ROOTCERT_FILE=$TESTNET/organizations/peerOrganizations/org2.example.com/peers/peer0.org2.example.com/tls/ca.crt
export CORE_PEER_MSPCONFIGPATH=$TESTNET/organizations/peerOrganizations/org2.example.com/users/Admin@org2.example.com/msp
export CORE_PEER_ADDRESS=localhost:9051
peer channel join -b ./channel-artifacts/mychannel.block 2>&1 | tail -1

echo "  [step] Deploy basic chaincode with OR endorsement..."
export GOPATH=/tmp/gopath
./network.sh deployCC -ccn basic -ccp ../asset-transfer-basic/chaincode-go -ccl go \
  -ccep "OR('Org1MSP.peer','Org2MSP.peer')" 2>&1 | grep -E 'committed|Approvals' | head -3

echo "  [done] Fresh network ready"
