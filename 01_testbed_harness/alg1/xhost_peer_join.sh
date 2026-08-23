#!/usr/bin/env bash
# Fix the peer join: the peer TLS cert SAN is peer0.org1.example.com (not the IP),
# so connect by FQDN. Add a hosts entry inside the container and join via FQDN.
set -u
KEY=/tmp/bk.pem; chmod 600 "$KEY" 2>/dev/null
SSH="ssh -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=15 -o BatchMode=yes"
H1=3.35.4.99
$SSH ubuntu@$H1 "sudo docker exec peer0 sh -c 'grep -q peer0.org1 /etc/hosts || echo \"127.0.0.1 peer0.org1.example.com\" >> /etc/hosts'"
echo "=== join via FQDN ==="
$SSH ubuntu@$H1 "sudo docker exec -e CORE_PEER_ADDRESS=peer0.org1.example.com:7051 -e CORE_PEER_MSPCONFIGPATH=/etc/hyperledger/fabric/adminmsp peer0 peer channel join -b /etc/hyperledger/fabric/mychannel.block 2>&1 | tail -2"
sleep 5
echo "=== channel list ==="
$SSH ubuntu@$H1 "sudo docker exec -e CORE_PEER_ADDRESS=peer0.org1.example.com:7051 -e CORE_PEER_MSPCONFIGPATH=/etc/hyperledger/fabric/adminmsp peer0 peer channel list 2>&1 | tail -3"
echo "PEER_JOIN_DONE"
