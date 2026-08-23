#!/usr/bin/env bash
# Submit one CreateAsset transaction directly, bypassing caliper, to separate
# "the network cannot endorse" from "caliper is misconfigured".
set -u
TN=/mnt/d/fabric-d2/fabric-samples/test-network
ORG1TLS=$TN/organizations/peerOrganizations/org1.example.com/tlsca/tlsca.org1.example.com-cert.pem
ORG2TLS=$TN/organizations/peerOrganizations/org2.example.com/tlsca/tlsca.org2.example.com-cert.pem
ORDCA=$TN/organizations/ordererOrganizations/example.com/tlsca/tlsca.example.com-cert.pem

echo "=== committed definition ==="
docker exec -e CORE_PEER_LOCALMSPID=Org1MSP -e CORE_PEER_MSPCONFIGPATH=/tmp/adminmsp \
  peer0.org1.example.com peer lifecycle chaincode querycommitted \
  --channelID mychannel --name basic 2>/dev/null | grep -E "Version|Endorsement"

echo "=== channel membership ==="
docker exec -e CORE_PEER_LOCALMSPID=Org1MSP -e CORE_PEER_MSPCONFIGPATH=/tmp/adminmsp \
  peer0.org1.example.com peer channel list 2>/dev/null | tail -2
docker exec -e CORE_PEER_LOCALMSPID=Org2MSP -e CORE_PEER_MSPCONFIGPATH=/tmp/adminmsp \
  peer0.org2.example.com peer channel list 2>/dev/null | tail -2

echo "=== direct invoke ==="
docker cp "$ORG2TLS" peer0.org1.example.com:/tmp/org2tls.pem >/dev/null 2>&1
docker cp "$ORDCA"  peer0.org1.example.com:/tmp/ordca.pem  >/dev/null 2>&1
docker exec -e CORE_PEER_LOCALMSPID=Org1MSP -e CORE_PEER_MSPCONFIGPATH=/tmp/adminmsp \
  -e CORE_PEER_ADDRESS=peer0.org1.example.com:7051 \
  -e CORE_PEER_TLS_ROOTCERT_FILE=/etc/hyperledger/fabric/tls/ca.crt \
  peer0.org1.example.com peer chaincode invoke \
    -o orderer.example.com:7050 --ordererTLSHostnameOverride orderer.example.com \
    --tls --cafile /tmp/ordca.pem -C mychannel -n basic \
    --peerAddresses peer0.org1.example.com:7051 \
    --tlsRootCertFiles /etc/hyperledger/fabric/tls/ca.crt \
    --peerAddresses peer0.org2.example.com:9051 \
    --tlsRootCertFiles /tmp/org2tls.pem \
    -c '{"function":"CreateAsset","Args":["probe1","blue","5","tester","10"]}' 2>&1 | tail -3
