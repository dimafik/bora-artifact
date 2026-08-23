#!/usr/bin/env bash
# Pull the orderer image on all 5 hosts in parallel.
chmod 600 /tmp/bk.pem 2>/dev/null
PUB=(43.201.73.122 54.180.99.165 43.201.25.172 54.180.117.221 15.164.226.99)
SSH="ssh -i /tmp/bk.pem -o StrictHostKeyChecking=no -o ConnectTimeout=15 -o BatchMode=yes"
for ip in "${PUB[@]}"; do
  $SSH ubuntu@$ip 'sudo docker pull hyperledger/fabric-orderer:latest >/tmp/pull.log 2>&1; echo "[$(hostname -I | awk "{print \$1}")] img=$(sudo docker images -q hyperledger/fabric-orderer:latest)"' 2>&1 | tail -1 &
done
wait
echo "PULL_DONE"
