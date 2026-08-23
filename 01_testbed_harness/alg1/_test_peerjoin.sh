#!/usr/bin/env bash
# Verify that a peer can join mychannel using the org Admin MSP copied into the
# container. Run from WSL. Prints JOIN_OK / JOIN_FAIL per peer.
set -u
TN=/mnt/d/fabric-d2/fabric-samples/test-network

try_join() {
  local pc="$1" mspid="$2" dom="$3" addr="$4"
  docker cp "$TN/channel-artifacts/mychannel.block" "$pc:/tmp/mychannel.block" >/dev/null 2>&1
  docker cp "$TN/organizations/peerOrganizations/$dom/users/Admin@$dom/msp" \
            "$pc:/tmp/adminmsp" >/dev/null 2>&1
  docker exec -e CORE_PEER_LOCALMSPID="$mspid" \
              -e CORE_PEER_MSPCONFIGPATH=/tmp/adminmsp \
              -e CORE_PEER_TLS_ROOTCERT_FILE=/etc/hyperledger/fabric/tls/ca.crt \
              -e CORE_PEER_ADDRESS="$addr" \
    "$pc" peer channel join -b /tmp/mychannel.block >/tmp/join_$mspid.log 2>&1
  sleep 4
  if docker exec -e CORE_PEER_LOCALMSPID="$mspid" -e CORE_PEER_MSPCONFIGPATH=/tmp/adminmsp \
       "$pc" peer channel list 2>/dev/null | grep -q mychannel; then
    echo "JOIN_OK $pc"
  else
    echo "JOIN_FAIL $pc"
    tail -2 /tmp/join_$mspid.log | sed 's/^/    /'
  fi
}

try_join peer0.org1.example.com Org1MSP org1.example.com peer0.org1.example.com:7051
try_join peer0.org2.example.com Org2MSP org2.example.com peer0.org2.example.com:9051
