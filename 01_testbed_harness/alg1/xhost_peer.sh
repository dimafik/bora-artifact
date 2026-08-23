#!/usr/bin/env bash
# C milestone 1: deploy one Org1 peer on host1 (alongside orderer1) and join mychannel.
# Throughput will then be driven by a peer-CLI invoke loop (milestone 3) after chaincode
# (milestone 2). Peer uses host networking; --add-host maps orderer names to private IPs.
set -u
KEY=/tmp/bk.pem; chmod 600 "$KEY" 2>/dev/null
SSH="ssh -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=15 -o BatchMode=yes"
SCP="scp -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=15 -q"
H1=3.35.4.99
TN=/mnt/d/fabric-d2/fabric-samples/test-network
PEER=$TN/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com
ADMSP=$TN/organizations/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp
GEN=/mnt/d/fabric-d2/results/xhost/mychannel.block
ADDH="--add-host orderer.example.com:172.31.39.233 --add-host orderer2.example.com:172.31.44.2 --add-host orderer3.example.com:172.31.37.115 --add-host orderer4.example.com:172.31.46.160 --add-host orderer5.example.com:172.31.39.145"

echo "=== pull fabric-peer on host1 ==="
$SSH ubuntu@$H1 'sudo docker pull hyperledger/fabric-peer:latest >/tmp/peerpull.log 2>&1; sudo docker images -q hyperledger/fabric-peer:latest'
echo "=== stage peer material to host1 ==="
$SSH ubuntu@$H1 'rm -rf ~/peer && mkdir -p ~/peer'
$SCP -r "$PEER/msp" ubuntu@$H1:~/peer/msp
$SCP -r "$PEER/tls" ubuntu@$H1:~/peer/tls
$SCP -r "$ADMSP" ubuntu@$H1:~/peer/adminmsp
$SCP "$GEN" ubuntu@$H1:~/peer/mychannel.block
echo "=== launch peer container ==="
$SSH ubuntu@$H1 "sudo docker rm -f peer0 >/dev/null 2>&1; sudo docker run -d --name peer0 --network host $ADDH \
  -e CORE_PEER_ID=peer0.org1.example.com -e CORE_PEER_ADDRESS=172.31.39.233:7051 \
  -e CORE_PEER_LISTENADDRESS=0.0.0.0:7051 -e CORE_PEER_CHAINCODEADDRESS=172.31.39.233:7052 \
  -e CORE_PEER_CHAINCODELISTENADDRESS=0.0.0.0:7052 \
  -e CORE_PEER_GOSSIP_BOOTSTRAP=172.31.39.233:7051 -e CORE_PEER_GOSSIP_EXTERNALENDPOINT=172.31.39.233:7051 \
  -e CORE_PEER_LOCALMSPID=Org1MSP -e CORE_PEER_MSPCONFIGPATH=/etc/hyperledger/fabric/msp \
  -e CORE_PEER_TLS_ENABLED=true -e CORE_PEER_TLS_CERT_FILE=/etc/hyperledger/fabric/tls/server.crt \
  -e CORE_PEER_TLS_KEY_FILE=/etc/hyperledger/fabric/tls/server.key -e CORE_PEER_TLS_ROOTCERT_FILE=/etc/hyperledger/fabric/tls/ca.crt \
  -e CORE_VM_ENDPOINT=unix:///host/var/run/docker.sock -e CORE_VM_DOCKER_HOSTCONFIG_NETWORKMODE=host \
  -e CORE_PEER_PROFILE_ENABLED=false -e FABRIC_LOGGING_SPEC=INFO \
  -e CORE_OPERATIONS_LISTENADDRESS=127.0.0.1:9444 \
  -v /home/ubuntu/peer/msp:/etc/hyperledger/fabric/msp -v /home/ubuntu/peer/tls:/etc/hyperledger/fabric/tls \
  -v /home/ubuntu/peer/adminmsp:/etc/hyperledger/fabric/adminmsp \
  -v /home/ubuntu/peer/mychannel.block:/etc/hyperledger/fabric/mychannel.block \
  -v /var/run/docker.sock:/host/var/run/docker.sock \
  hyperledger/fabric-peer:latest peer node start >/dev/null 2>&1 && echo launched || echo LAUNCH_FAIL"
sleep 12
echo "  peer0 status: $($SSH ubuntu@$H1 'sudo docker inspect -f "{{.State.Status}} r={{.RestartCount}}" peer0 2>/dev/null')"
echo "=== peer channel join (admin MSP) ==="
$SSH ubuntu@$H1 "sudo docker exec -e CORE_PEER_MSPCONFIGPATH=/etc/hyperledger/fabric/adminmsp peer0 peer channel join -b /etc/hyperledger/fabric/mychannel.block 2>&1 | tail -2"
sleep 5
echo "=== channels on peer ==="
$SSH ubuntu@$H1 "sudo docker exec -e CORE_PEER_MSPCONFIGPATH=/etc/hyperledger/fabric/adminmsp peer0 peer channel list 2>&1 | tail -3"
echo "XHOST_PEER_DONE"