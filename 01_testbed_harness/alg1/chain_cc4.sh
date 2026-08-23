#!/usr/bin/env bash
# Wait until chaincode 'basic' is COMMITTED (Step 3 done by the other chain), then
# run Step 4 throughput automatically. Gentle 30s polling to spare the busy t3.micro.
KEY=/tmp/bk.pem; chmod 600 "$KEY" 2>/dev/null
SSH="ssh -i $KEY -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=25"
PE1="-e CORE_PEER_ADDRESS=peer0.org1.example.com:7051 -e CORE_PEER_MSPCONFIGPATH=/etc/hyperledger/fabric/adminmsp"
for i in $(seq 1 80); do
  r=$($SSH ubuntu@3.35.4.99 "sudo docker exec $PE1 peer0 peer lifecycle chaincode querycommitted --channelID mychannel --name basic 2>&1 | grep -oE 'Version: 1.0|not defined'" 2>/dev/null | head -1)
  echo "[$i] committed? ${r:-?}"
  if [ "$r" = "Version: 1.0" ]; then echo "CHAINCODE_COMMITTED"; break; fi
  sleep 30
done
echo "=== launching Step 4 throughput ==="
bash /mnt/d/fabric-d2/alg1/xhost_throughput.sh 30 baseline
echo "CHAIN_CC4_DONE"
