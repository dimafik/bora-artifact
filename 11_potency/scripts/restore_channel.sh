#!/usr/bin/env bash
# Rejoin the peers to mychannel and recommit chaincode, so throughput can be
# measured again.
#
# The orderers still carry mychannel (chains/mychannel exists) but the peers'
# ledger directory is empty, so the channel has to be joined from the genesis
# block and the chaincode recommitted -- a channel-level commit does not survive
# a wiped peer ledger.
#
# Neither the host nor WSL has the peer CLI or Go, so every command runs inside
# the peer container, and the Admin MSP is mounted in rather than reissued: the
# container's own identity is not an Org admin and lifecycle calls fail the ACL
# check.  Packaging is skipped entirely because test-network/basic.tar.gz was
# built earlier and is still on disk.
#
# Run this only when no election campaign is in flight: it submits configuration
# and chaincode transactions, and a paused orderer mid-join produces a partial
# channel that is harder to clean up than to avoid.
set -u

TN=/d/fabric-d2/fabric-samples/test-network
ORG=$TN/organizations
CH=mychannel
CC=basic

ORDERER_CA_C=/etc/hyperledger/orderer-ca.pem
ADMIN1_C=/etc/hyperledger/admin1
ADMIN2_C=/etc/hyperledger/admin2

step(){ printf "\n=== %s ===\n" "$*"; }

# Everything runs through a throwaway CLI container that has the peer binary,
# the admin identities and the orderer TLS root, so the long-lived peers are
# never reconfigured.
cli(){ # $1=org (1|2) ; rest = peer command
  local org="$1"; shift
  local addr msp mspid ca
  if [ "$org" = 1 ]; then
    addr=peer0.org1.example.com:7051; mspid=Org1MSP; msp=$ADMIN1_C
    ca=/etc/hyperledger/org1-ca.pem
  else
    addr=peer0.org2.example.com:9051; mspid=Org2MSP; msp=$ADMIN2_C
    ca=/etc/hyperledger/org2-ca.pem
  fi
  MSYS_NO_PATHCONV=1 docker run --rm --network fabric_test \
    -v "$ORG":/etc/hyperledger/org \
    -v "$ORG/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp":$ADMIN1_C \
    -v "$ORG/peerOrganizations/org2.example.com/users/Admin@org2.example.com/msp":$ADMIN2_C \
    -v "$ORG/ordererOrganizations/example.com/orderers/orderer.example.com/msp/tlscacerts/tlsca.example.com-cert.pem":$ORDERER_CA_C \
    -v "$ORG/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt":/etc/hyperledger/org1-ca.pem \
    -v "$ORG/peerOrganizations/org2.example.com/peers/peer0.org2.example.com/tls/ca.crt":/etc/hyperledger/org2-ca.pem \
    -v /d/fabric-d2/results/restore:/work \
    -w /work \
    -e CORE_PEER_TLS_ENABLED=true \
    -e CORE_PEER_LOCALMSPID="$mspid" \
    -e CORE_PEER_MSPCONFIGPATH="$msp" \
    -e CORE_PEER_ADDRESS="$addr" \
    -e CORE_PEER_TLS_ROOTCERT_FILE="$ca" \
    hyperledger/fabric-tools:2.5 "$@"
}

mkdir -p /d/fabric-d2/results/restore
cp "$TN/basic.tar.gz" /d/fabric-d2/results/restore/ 2>/dev/null

step "1. fetch genesis block"
cli 1 peer channel fetch 0 "$CH.block" -c "$CH" \
    -o orderer.example.com:7050 --ordererTLSHostnameOverride orderer.example.com \
    --tls --cafile "$ORDERER_CA_C" 2>&1 | tail -3

step "2. join both peers"
cli 1 peer channel join -b "$CH.block" 2>&1 | tail -2
cli 2 peer channel join -b "$CH.block" 2>&1 | tail -2

step "3. joined channels"
cli 1 peer channel list 2>&1 | tail -3
cli 2 peer channel list 2>&1 | tail -3

step "4. install chaincode (prebuilt package)"
cli 1 peer lifecycle chaincode install basic.tar.gz 2>&1 | tail -2
cli 2 peer lifecycle chaincode install basic.tar.gz 2>&1 | tail -2

PKGID=$(cli 1 peer lifecycle chaincode queryinstalled 2>&1 \
        | sed -n 's/^Package ID: \(basic_1.0:[a-f0-9]*\),.*/\1/p' | head -1)
echo "PKGID=$PKGID"
[ -n "$PKGID" ] || { echo "INSTALL_FAILED"; exit 1; }

step "5. approve for both orgs"
for o in 1 2; do
  cli $o peer lifecycle chaincode approveformyorg \
      -o orderer.example.com:7050 --ordererTLSHostnameOverride orderer.example.com \
      --channelID "$CH" --name "$CC" --version 1.0 --package-id "$PKGID" \
      --sequence 1 --tls --cafile "$ORDERER_CA_C" 2>&1 | tail -2
done

step "6. commit"
cli 1 peer lifecycle chaincode commit \
    -o orderer.example.com:7050 --ordererTLSHostnameOverride orderer.example.com \
    --channelID "$CH" --name "$CC" --version 1.0 --sequence 1 \
    --tls --cafile "$ORDERER_CA_C" \
    --peerAddresses peer0.org1.example.com:7051 \
      --tlsRootCertFiles /etc/hyperledger/org1-ca.pem \
    --peerAddresses peer0.org2.example.com:9051 \
      --tlsRootCertFiles /etc/hyperledger/org2-ca.pem 2>&1 | tail -3

step "7. verify"
cli 1 peer lifecycle chaincode querycommitted --channelID "$CH" --name "$CC" 2>&1 | tail -3
cli 1 peer channel getinfo -c "$CH" 2>&1 | tail -1
echo "RESTORE_DONE"
