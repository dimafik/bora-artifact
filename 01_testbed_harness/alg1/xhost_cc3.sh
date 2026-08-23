#!/usr/bin/env bash
# C step 3 (clean quoting): install package on both peers, approve (Org1+Org2),
# commit, querycommitted. ccenv:3.1 + baseos:3.1 already on both hosts.
set -u
KEY=/tmp/bk.pem; chmod 600 "$KEY" 2>/dev/null
SSH="ssh -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=25 -o BatchMode=yes"
SCP="scp -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=25 -q"
H1=3.35.4.99; H2=15.165.203.234
TN=/mnt/d/fabric-d2/fabric-samples/test-network
ORDCA=/mnt/d/fabric-d2/results/xhost/orderer-ca.pem
ORG1CA=$TN/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt
ORG2CA=$TN/organizations/peerOrganizations/org2.example.com/peers/peer0.org2.example.com/tls/ca.crt
PE1="-e CORE_PEER_ADDRESS=peer0.org1.example.com:7051 -e CORE_PEER_MSPCONFIGPATH=/etc/hyperledger/fabric/adminmsp"
PE2="-e CORE_PEER_ADDRESS=peer0.org2.example.com:7051 -e CORE_PEER_MSPCONFIGPATH=/etc/hyperledger/fabric/adminmsp"
ORDF="--orderer orderer.example.com:7050 --tls --cafile /tmp/ord-ca.crt --ordererTLSHostnameOverride orderer.example.com"
SP="--signature-policy OR('Org1MSP.member','Org2MSP.member')"

echo "=== stage package + CAs ==="
$SCP ubuntu@$H1:/home/ubuntu/basic.tar.gz /tmp/basic.tar.gz
$SCP /tmp/basic.tar.gz ubuntu@$H2:/home/ubuntu/basic.tar.gz
$SCP "$ORDCA" ubuntu@$H1:/home/ubuntu/ord-ca.crt; $SCP "$ORDCA" ubuntu@$H2:/home/ubuntu/ord-ca.crt
$SCP "$ORG1CA" ubuntu@$H1:/home/ubuntu/org1-ca.crt; $SCP "$ORG2CA" ubuntu@$H1:/home/ubuntu/org2-ca.crt
$SSH ubuntu@$H1 "sudo docker cp /home/ubuntu/ord-ca.crt peer0:/tmp/ord-ca.crt; sudo docker cp /home/ubuntu/org1-ca.crt peer0:/tmp/org1-ca.crt; sudo docker cp /home/ubuntu/org2-ca.crt peer0:/tmp/org2-ca.crt"
$SSH ubuntu@$H2 "sudo docker cp /home/ubuntu/ord-ca.crt peer0:/tmp/ord-ca.crt; sudo docker cp /home/ubuntu/basic.tar.gz peer0:/tmp/basic.tar.gz"
# org1 peer must resolve peer0.org2 -> host2 private IP for the cross-peer commit endorsement
$SSH ubuntu@$H1 "sudo docker exec peer0 bash -c 'grep -q peer0.org2 /etc/hosts || echo \"172.31.44.2 peer0.org2.example.com\" >> /etc/hosts'"

echo "=== install on both peers (ccenv build, minutes) ==="
$SSH ubuntu@$H1 "sudo docker exec $PE1 peer0 peer lifecycle chaincode install /tmp/basic.tar.gz 2>&1 | tail -1"
$SSH ubuntu@$H2 "sudo docker exec $PE2 peer0 peer lifecycle chaincode install /tmp/basic.tar.gz 2>&1 | tail -1"
PKG=$($SSH ubuntu@$H1 "sudo docker exec $PE1 peer0 peer lifecycle chaincode queryinstalled 2>&1 | grep -oE 'basic_1:[a-f0-9]+' | head -1")
echo "  package-id: ${PKG:-NONE}"
[ -z "$PKG" ] && { echo "NO_PKGID_ABORT"; exit 1; }

echo "=== approve Org1, Org2 ==="
$SSH ubuntu@$H1 "sudo docker exec $PE1 peer0 peer lifecycle chaincode approveformyorg $ORDF --channelID mychannel --name basic --version 1.0 --package-id $PKG --sequence 1 $SP 2>&1 | tail -1"
$SSH ubuntu@$H2 "sudo docker exec $PE2 peer0 peer lifecycle chaincode approveformyorg $ORDF --channelID mychannel --name basic --version 1.0 --package-id $PKG --sequence 1 $SP 2>&1 | tail -1"
echo "=== checkcommitreadiness ==="
$SSH ubuntu@$H1 "sudo docker exec $PE1 peer0 peer lifecycle chaincode checkcommitreadiness --channelID mychannel --name basic --version 1.0 --sequence 1 $SP 2>&1 | tail -3"
echo "=== commit (both orgs endorse) ==="
$SSH ubuntu@$H1 "sudo docker exec $PE1 peer0 peer lifecycle chaincode commit $ORDF --channelID mychannel --name basic --version 1.0 --sequence 1 $SP --peerAddresses peer0.org1.example.com:7051 --tlsRootCertFiles /tmp/org1-ca.crt --peerAddresses peer0.org2.example.com:7051 --tlsRootCertFiles /tmp/org2-ca.crt 2>&1 | tail -2"
sleep 4
$SSH ubuntu@$H1 "sudo docker exec $PE1 peer0 peer lifecycle chaincode querycommitted --channelID mychannel --name basic 2>&1 | tail -2"
echo "XHOST_CC3_DONE"
