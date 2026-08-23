#!/usr/bin/env bash
# Task 3: restart peers, scp the concurrent-load script, run it for real tx/s.
set -u
KEY=/tmp/bk.pem; chmod 600 "$KEY" 2>/dev/null
SSH="ssh -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=25 -o BatchMode=yes"
SCP="scp -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=25 -q"
H1=15.164.215.28; H2=13.209.97.224
PE1="-e CORE_PEER_ADDRESS=peer0.org1.example.com:7051 -e CORE_PEER_MSPCONFIGPATH=/etc/hyperledger/fabric/adminmsp"
INVW="--orderer orderer.example.com:7050 --tls --cafile /tmp/ord-ca.crt --ordererTLSHostnameOverride orderer.example.com -C mychannel -n basic --peerAddresses peer0.org1.example.com:7051 --tlsRootCertFiles /tmp/org1-ca.crt --peerAddresses peer0.org2.example.com:7051 --tlsRootCertFiles /tmp/org2-ca.crt"

echo "=== restart peers ==="
echo "  org1: $($SSH ubuntu@$H1 'sudo docker start peer0 >/dev/null 2>&1; sudo docker inspect -f "{{.State.Status}}" peer0')"
echo "  org2: $($SSH ubuntu@$H2 'sudo docker start peer0 >/dev/null 2>&1; sudo docker inspect -f "{{.State.Status}}" peer0')"
sleep 14
echo "=== warmup (re-spawn chaincode container; may take ~30s) ==="
$SSH ubuntu@$H1 "sudo docker exec $PE1 peer0 peer chaincode invoke $INVW -c '{\"function\":\"CreateAsset\",\"Args\":[\"warm_t3\",\"b\",\"1\",\"x\",\"1\"]}' --waitForEvent 2>&1 | grep -oE 'status:[0-9]+|Error.*' | head -1"
sleep 3
$SCP /mnt/d/fabric-d2/alg1/t3_remote.sh ubuntu@$H1:/tmp/t3_remote.sh
echo "=== concurrent throughput sweep ==="
for par in 1 4 8 12; do
  r=$($SSH ubuntu@$H1 "bash /tmp/t3_remote.sh $par 6 base 2>&1 | tail -1")
  echo "  $r"
done
echo "XHOST_T3_DONE"
