#!/usr/bin/env bash
# host1 disk is 91% full (2G swapfile eats it) so ccenv:3.1 won't pull. Shrink swap
# to 1G (frees ~1G), clean apt cache, then pull ccenv/baseos 3.1.
KEY=/tmp/bk.pem; chmod 600 "$KEY" 2>/dev/null
SSH="ssh -i $KEY -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=30"
H1=3.35.4.99
$SSH ubuntu@$H1 'sudo swapoff /swapfile 2>/dev/null; sudo rm -f /swapfile; sudo fallocate -l 1G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile >/dev/null && sudo swapon /swapfile; sudo apt-get clean; df -h / | tail -1; free -m | grep -i swap'
echo "=== pull ccenv/baseos 3.1 on host1 ==="
$SSH ubuntu@$H1 'sudo docker pull hyperledger/fabric-ccenv:3.1 >/tmp/cc.log 2>&1; sudo docker pull hyperledger/fabric-baseos:3.1 >/tmp/bo.log 2>&1; echo ccenv=$(sudo docker images -q hyperledger/fabric-ccenv:3.1) baseos=$(sudo docker images -q hyperledger/fabric-baseos:3.1); tail -1 /tmp/cc.log; df -h / | tail -1'
echo "FIX_HOST1_DONE"
