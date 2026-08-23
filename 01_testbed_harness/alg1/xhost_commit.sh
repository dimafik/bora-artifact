#!/usr/bin/env bash
# approve (Org1+Org2) + commit using the DEFAULT (majority) endorsement policy to
# avoid the OR(...) shell-paren issue. Chaincode already installed on both peers.
set -u
KEY=/tmp/bk.pem; chmod 600 "$KEY" 2>/dev/null
SSH="ssh -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=25 -o BatchMode=yes"
H1=3.35.4.99; H2=15.165.203.234
PKG=basic_1:242ad801c34d23e618c725dc7a97bd3d94a275ccc2a16a839ba37f9413b00e9b
PE1="-e CORE_PEER_ADDRESS=peer0.org1.example.com:7051 -e CORE_PEER_MSPCONFIGPATH=/etc/hyperledger/fabric/adminmsp"
PE2="-e CORE_PEER_ADDRESS=peer0.org2.example.com:7051 -e CORE_PEER_MSPCONFIGPATH=/etc/hyperledger/fabric/adminmsp"
ORDF="--orderer orderer.example.com:7050 --tls --cafile /tmp/ord-ca.crt --ordererTLSHostnameOverride orderer.example.com"
CC="--channelID mychannel --name basic --version 1.0 --sequence 1"

echo "=== approve Org1 ==="
$SSH ubuntu@$H1 "sudo docker exec $PE1 peer0 peer lifecycle chaincode approveformyorg $ORDF $CC --package-id $PKG 2>&1 | tail -1"
echo "=== approve Org2 ==="
$SSH ubuntu@$H2 "sudo docker exec $PE2 peer0 peer lifecycle chaincode approveformyorg $ORDF $CC --package-id $PKG 2>&1 | tail -1"
echo "=== checkcommitreadiness ==="
$SSH ubuntu@$H1 "sudo docker exec $PE1 peer0 peer lifecycle chaincode checkcommitreadiness $CC 2>&1 | tail -3"
echo "=== commit (both orgs endorse) ==="
$SSH ubuntu@$H1 "sudo docker exec $PE1 peer0 peer lifecycle chaincode commit $ORDF $CC --peerAddresses peer0.org1.example.com:7051 --tlsRootCertFiles /tmp/org1-ca.crt --peerAddresses peer0.org2.example.com:7051 --tlsRootCertFiles /tmp/org2-ca.crt 2>&1 | tail -2"
sleep 4
echo "=== querycommitted ==="
$SSH ubuntu@$H1 "sudo docker exec $PE1 peer0 peer lifecycle chaincode querycommitted --channelID mychannel --name basic 2>&1 | tail -3"
echo "XHOST_COMMIT_DONE"
