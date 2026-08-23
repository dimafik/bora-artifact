#!/usr/bin/env bash
# C step 1 (retry): install Go on host1, package the golang chaincode on the host
# (peer CLI needs Go to resolve the module), then install into peer0 (ccenv build,
# 2G swap already added). fabric-peer image has no Go, hence host-side packaging.
set -u
KEY=/tmp/bk.pem; chmod 600 "$KEY" 2>/dev/null
SSH="ssh -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=20 -o BatchMode=yes"
H1=3.35.4.99
PE="-e CORE_PEER_ADDRESS=peer0.org1.example.com:7051 -e CORE_PEER_MSPCONFIGPATH=/etc/hyperledger/fabric/adminmsp"

echo "=== install Go on host1 ==="
$SSH ubuntu@$H1 'sudo DEBIAN_FRONTEND=noninteractive apt-get install -y golang-go >/tmp/go.log 2>&1; go version 2>&1 || /usr/lib/go-*/bin/go version 2>&1 | head -1'
echo "=== extract peer CLI + core.yaml from image ==="
$SSH ubuntu@$H1 'sudo docker cp peer0:/usr/local/bin/peer /home/ubuntu/peer-cli && sudo chmod +x /home/ubuntu/peer-cli; mkdir -p /home/ubuntu/fabriccfg; sudo docker cp peer0:/etc/hyperledger/fabric/core.yaml /home/ubuntu/fabriccfg/core.yaml; ls -la /home/ubuntu/peer-cli /home/ubuntu/fabriccfg/core.yaml'
echo "=== package chaincode on host (Go available) ==="
$SSH ubuntu@$H1 'export PATH=$PATH:/usr/lib/go-*/bin:/usr/bin; cd /home/ubuntu/cc/chaincode-go && (go mod vendor >/tmp/vendor.log 2>&1 || true); FABRIC_CFG_PATH=/home/ubuntu/fabriccfg /home/ubuntu/peer-cli lifecycle chaincode package /home/ubuntu/basic.tar.gz --path /home/ubuntu/cc/chaincode-go --lang golang --label basic_1 2>&1 | tail -3; ls -la /home/ubuntu/basic.tar.gz 2>&1'
echo "=== copy package into peer0 + pull ccenv ==="
$SSH ubuntu@$H1 'sudo docker cp /home/ubuntu/basic.tar.gz peer0:/tmp/basic.tar.gz; sudo docker pull hyperledger/fabric-ccenv:latest >/tmp/ccenv.log 2>&1 & echo ccenv-pull-bg'
echo "=== install (ccenv build, may take minutes) ==="
$SSH ubuntu@$H1 "sudo docker exec $PE peer0 peer lifecycle chaincode install /tmp/basic.tar.gz 2>&1 | tail -3"
$SSH ubuntu@$H1 "sudo docker exec $PE peer0 peer lifecycle chaincode queryinstalled 2>&1 | tail -3"
echo "XHOST_CC2_DONE"
