#!/usr/bin/env bash
# C step 2: deploy an Org2 peer on host2 (alongside orderer2) and join mychannel, so
# the default majority-of-orgs lifecycle endorsement policy can be satisfied at commit.
set -u
KEY=/tmp/bk.pem; chmod 600 "$KEY" 2>/dev/null
SSH="ssh -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=15 -o BatchMode=yes"
SCP="scp -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=15 -q -r"
H2=15.165.203.234
PRIV2=172.31.44.2
TN=/mnt/d/fabric-d2/fabric-samples/test-network
PEER=$TN/organizations/peerOrganizations/org2.example.com/peers/peer0.org2.example.com
ADMSP=$TN/organizations/peerOrganizations/org2.example.com/users/Admin@org2.example.com/msp
GEN=/mnt/d/fabric-d2/results/xhost/mychannel.block
ADDH="--add-host orderer.example.com:172.31.39.233 --add-host orderer2.example.com:172.31.44.2 --add-host orderer3.example.com:172.31.37.115 --add-host orderer4.example.com:172.31.46.160 --add-host orderer5.example.com:172.31.39.145 --add-host peer0.org2.example.com:127.0.0.1"

$SSH ubuntu@$H2 'sudo docker pull hyperledger/fabric-peer:latest >/tmp/pp.log 2>&1; rm -rf ~/peer && mkdir -p ~/peer'
$SCP "$PEER/msp" ubuntu@$H2:~/peer/msp
$SCP "$PEER/tls" ubuntu@$H2:~/peer/tls
$SCP "$ADMSP" ubuntu@$H2:~/peer/adminmsp
$SCP "$GEN" ubuntu@$H2:~/peer/mychannel.block
$SSH ubuntu@$H2 "sudo docker rm -f peer0 >/dev/null 2>&1; sudo docker run -d --name peer0 --network host $ADDH \
  -e CORE_PEER_ID=peer0.org2.example.com -e CORE_PEER_ADDRESS=$PRIV2:7051 \
  -e CORE_PEER_LISTENADDRESS=0.0.0.0:7051 -e CORE_PEER_CHAINCODEADDRESS=$PRIV2:7052 \
  -e CORE_PEER_CHAINCODELISTENADDRESS=0.0.0.0:7052 \
  -e CORE_PEER_GOSSIP_BOOTSTRAP=$PRIV2:7051 -e CORE_PEER_GOSSIP_EXTERNALENDPOINT=$PRIV2:7051 \
  -e CORE_PEER_LOCALMSPID=Org2MSP -e CORE_PEER_MSPCONFIGPATH=/etc/hyperledger/fabric/msp \
  -e CORE_PEER_TLS_ENABLED=true -e CORE_PEER_TLS_CERT_FILE=/etc/hyperledger/fabric/tls/server.crt \
  -e CORE_PEER_TLS_KEY_FILE=/etc/hyperledger/fabric/tls/server.key -e CORE_PEER_TLS_ROOTCERT_FILE=/etc/hyperledger/fabric/tls/ca.crt \
  -e CORE_VM_ENDPOINT=unix:///host/var/run/docker.sock -e CORE_VM_DOCKER_HOSTCONFIG_NETWORKMODE=host \
  -e FABRIC_LOGGING_SPEC=INFO -e CORE_OPERATIONS_LISTENADDRESS=127.0.0.1:9444 \
  -v /home/ubuntu/peer/msp:/etc/hyperledger/fabric/msp -v /home/ubuntu/peer/tls:/etc/hyperledger/fabric/tls \
  -v /home/ubuntu/peer/adminmsp:/etc/hyperledger/fabric/adminmsp \
  -v /home/ubuntu/peer/mychannel.block:/etc/hyperledger/fabric/mychannel.block \
  -v /var/run/docker.sock:/host/var/run/docker.sock \
  hyperledger/fabric-peer:latest peer node start >/dev/null 2>&1 && echo launched || echo LAUNCH_FAIL"
sleep 12
$SSH ubuntu@$H2 'sudo docker exec peer0 sh -c "grep -q peer0.org2 /etc/hosts || echo 127.0.0.1 peer0.org2.example.com >> /etc/hosts"'
echo "  peer0(org2) status: $($SSH ubuntu@$H2 'sudo docker inspect -f "{{.State.Status}} r={{.RestartCount}}" peer0 2>/dev/null')"
echo "=== org2 peer channel join ==="
$SSH ubuntu@$H2 "sudo docker exec -e CORE_PEER_ADDRESS=peer0.org2.example.com:7051 -e CORE_PEER_MSPCONFIGPATH=/etc/hyperledger/fabric/adminmsp peer0 peer channel join -b /etc/hyperledger/fabric/mychannel.block 2>&1 | tail -2"
sleep 4
$SSH ubuntu@$H2 "sudo docker exec -e CORE_PEER_ADDRESS=peer0.org2.example.com:7051 -e CORE_PEER_MSPCONFIGPATH=/etc/hyperledger/fabric/adminmsp peer0 peer channel list 2>&1 | tail -2"
echo "XHOST_PEER2_DONE"
