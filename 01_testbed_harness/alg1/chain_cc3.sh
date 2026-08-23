#!/usr/bin/env bash
# Wait until ccenv:3.1 is present on host1 (and host2), then run Step 3 automatically.
KEY=/tmp/bk.pem; chmod 600 "$KEY" 2>/dev/null
SSH="ssh -i $KEY -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=20"
for i in $(seq 1 60); do
  c1=$($SSH ubuntu@3.35.4.99 'sudo docker images -q hyperledger/fabric-ccenv:3.1' 2>/dev/null)
  c2=$($SSH ubuntu@15.165.203.234 'sudo docker images -q hyperledger/fabric-ccenv:3.1' 2>/dev/null)
  b1=$($SSH ubuntu@3.35.4.99 'sudo docker images -q hyperledger/fabric-baseos:3.1' 2>/dev/null)
  echo "[$i] host1 ccenv=$c1 baseos=$b1 | host2 ccenv=$c2"
  if [ -n "$c1" ] && [ -n "$c2" ] && [ -n "$b1" ]; then echo "CCENV_READY"; break; fi
  sleep 15
done
echo "=== launching Step 3 ==="
bash /mnt/d/fabric-d2/alg1/xhost_cc3.sh
echo "CHAIN_CC3_DONE"
