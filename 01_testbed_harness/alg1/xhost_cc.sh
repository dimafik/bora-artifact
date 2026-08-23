#!/usr/bin/env bash
# C milestone 2: add swap (t3.micro has none -> Go build OOMs without it), then
# package + install + approve + commit asset-transfer-basic chaincode-go on the
# cross-host network (peer0 on host1, orderers across 5 hosts).
set -u
KEY=/tmp/bk.pem; chmod 600 "$KEY" 2>/dev/null
SSH="ssh -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=15 -o BatchMode=yes"
SCP="scp -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=15 -q -r"
H1=3.35.4.99
CC=/mnt/d/fabric-d2/fabric-samples/asset-transfer-basic/chaincode-go
OCA=/etc/hyperledger/fabric/tls/ca.crt   # not used; orderer CA path below
PE="-e CORE_PEER_ADDRESS=peer0.org1.example.com:7051 -e CORE_PEER_MSPCONFIGPATH=/etc/hyperledger/fabric/adminmsp"

echo "=== add 2G swap on host1 ==="
$SSH ubuntu@$H1 'if ! sudo swapon --show | grep -q swapfile; then sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile >/dev/null && sudo swapon /swapfile; fi; free -m | grep -i swap'
echo "=== stage chaincode + orderer CA to host1 ==="
$SSH ubuntu@$H1 'rm -rf ~/cc && mkdir -p ~/cc'
$SCP "$CC" ubuntu@$H1:~/cc/chaincode-go
$SSH ubuntu@$H1 'sudo docker cp orderer:/var/hyperledger/orderer/tls/ca.crt /tmp/ord-ca.crt 2>/dev/null; sudo docker cp /tmp/ord-ca.crt peer0:/tmp/ord-ca.crt'
$SSH ubuntu@$H1 'sudo docker exec peer0 mkdir -p /opt/cc; sudo docker cp /home/ubuntu/cc/chaincode-go peer0:/opt/cc/chaincode-go'
echo "=== package ==="
$SSH ubuntu@$H1 "sudo docker exec $PE peer0 peer lifecycle chaincode package /tmp/basic.tar.gz --path /opt/cc/chaincode-go --lang golang --label basic_1 2>&1 | tail -2"
echo "=== install (builds chaincode; ~minutes) ==="
$SSH ubuntu@$H1 "sudo docker exec $PE peer0 peer lifecycle chaincode install /tmp/basic.tar.gz 2>&1 | tail -3"
echo "=== queryinstalled ==="
$SSH ubuntu@$H1 "sudo docker exec $PE peer0 peer lifecycle chaincode queryinstalled 2>&1 | tail -3"
echo "XHOST_CC_INSTALL_DONE"
