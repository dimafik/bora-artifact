#!/bin/bash
# Join channel on all 5 orderers + 2 peers, deploy basic chaincode
set -e
cd /mnt/d/fabric-d2/fabric-samples/test-network
export PATH=/tmp/bin:/tmp/go-install/go/bin:/mnt/d/fabric-d2/fabric-samples/bin-linux/bin:/usr/local/bin:/usr/bin:/bin
export FABRIC_CFG_PATH=/mnt/d/fabric-d2/fabric-samples/config

ORDERER_CA=organizations/ordererOrganizations/example.com/orderers/orderer.example.com/msp/tlscacerts/tlsca.example.com-cert.pem

echo "=== STEP 1 osnadmin join channel on each orderer ==="
for n in 1 2 3 4 5; do
  case $n in
    1) ADM=7053  ;;
    2) ADM=8053  ;;
    3) ADM=10053 ;;
    4) ADM=11053 ;;
    5) ADM=12053 ;;
  esac
  if [ "$n" = "1" ]; then
    HOST=orderer
  else
    HOST=orderer$n
  fi
  echo "--- orderer$n (admin :$ADM) ---"
  CERT=organizations/ordererOrganizations/example.com/orderers/${HOST}.example.com/tls/server.crt
  KEY=organizations/ordererOrganizations/example.com/orderers/${HOST}.example.com/tls/server.key
  osnadmin channel join \
    --channelID mychannel \
    --config-block ./channel-artifacts/mychannel.block \
    -o localhost:$ADM \
    --ca-file "$ORDERER_CA" \
    --client-cert "$CERT" \
    --client-key "$KEY" 2>&1 | tail -7
  echo ""
done

echo "=== STEP 2 osnadmin channel list (each orderer) ==="
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
  CHANS=$(osnadmin channel list -o localhost:$ADM --ca-file "$ORDERER_CA" --client-cert "$CERT" --client-key "$KEY" 2>&1 | grep -o 'mychannel' | head -1)
  echo "orderer$n (:$ADM): channels = ${CHANS:-NONE}"
done

echo ""
echo "=== STEP 3 Peer Org1 join channel ==="
export CORE_PEER_TLS_ENABLED=true
export CORE_PEER_LOCALMSPID="Org1MSP"
export CORE_PEER_TLS_ROOTCERT_FILE=$PWD/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt
export CORE_PEER_MSPCONFIGPATH=$PWD/organizations/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp
export CORE_PEER_ADDRESS=localhost:7051
peer channel join -b ./channel-artifacts/mychannel.block 2>&1 | tail -3

echo "=== STEP 4 Peer Org2 join channel ==="
export CORE_PEER_LOCALMSPID="Org2MSP"
export CORE_PEER_TLS_ROOTCERT_FILE=$PWD/organizations/peerOrganizations/org2.example.com/peers/peer0.org2.example.com/tls/ca.crt
export CORE_PEER_MSPCONFIGPATH=$PWD/organizations/peerOrganizations/org2.example.com/users/Admin@org2.example.com/msp
export CORE_PEER_ADDRESS=localhost:9051
peer channel join -b ./channel-artifacts/mychannel.block 2>&1 | tail -3
