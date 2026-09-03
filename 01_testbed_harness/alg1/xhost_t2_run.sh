#!/usr/bin/env bash
# Unpause any leftover-paused orderer, then run task 2.
cp "${BORA_KEY:?set BORA_KEY to your EC2 private key}" /tmp/bk.pem 2>/dev/null; chmod 600 /tmp/bk.pem
SSH="ssh -i /tmp/bk.pem -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=15 -o ServerAliveInterval=5"
for ip in 15.164.215.28 13.209.97.224 13.209.3.44 54.180.145.47 52.78.184.161; do
  $SSH "ubuntu@$ip" 'sudo docker unpause orderer 2>/dev/null; true' >/dev/null 2>&1
done
echo "unpaused all; starting task 2"
bash /mnt/d/fabric-d2/alg1/xhost_t2.sh
