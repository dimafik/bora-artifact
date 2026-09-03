#!/usr/bin/env bash
# Task 3 (fixed): docker start regenerates /etc/hosts, dropping our peer FQDN entries.
# Re-add them, validate the warmup commits (status:200), then run the concurrent sweep.
set -u
cp "${BORA_KEY:?set BORA_KEY to your EC2 private key}" /tmp/bk.pem 2>/dev/null; chmod 600 /tmp/bk.pem
SSH="ssh -i /tmp/bk.pem -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=15 -o ServerAliveInterval=5 -o ServerAliveCountMax=3"
SCP="scp -i /tmp/bk.pem -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=15 -q"
H1=15.164.215.28; H2=13.209.97.224
PE1="-e CORE_PEER_ADDRESS=peer0.org1.example.com:7051 -e CORE_PEER_MSPCONFIGPATH=/etc/hyperledger/fabric/adminmsp"
INVW="--orderer orderer.example.com:7050 --tls --cafile /tmp/ord-ca.crt --ordererTLSHostnameOverride orderer.example.com -C mychannel -n basic --peerAddresses peer0.org1.example.com:7051 --tlsRootCertFiles /tmp/org1-ca.crt --peerAddresses peer0.org2.example.com:7051 --tlsRootCertFiles /tmp/org2-ca.crt"
OUT=/mnt/d/fabric-d2/results/xhost_t3b_$(date +%H%M%S); mkdir -p "$OUT"

echo "=== ensure peers running + repair /etc/hosts (FQDN -> IP) ==="
$SSH ubuntu@$H1 'sudo docker start peer0 >/dev/null 2>&1; true'
$SSH ubuntu@$H2 'sudo docker start peer0 >/dev/null 2>&1; true'
sleep 10
# org1 peer must resolve its own FQDN (127.0.0.1) and the org2 peer (host2 priv IP)
$SSH ubuntu@$H1 'sudo docker exec peer0 bash -c "grep -q peer0.org1 /etc/hosts || echo 127.0.0.1 peer0.org1.example.com >> /etc/hosts; grep -q peer0.org2 /etc/hosts || echo 172.31.44.2 peer0.org2.example.com >> /etc/hosts"'
$SSH ubuntu@$H1 'sudo docker exec peer0 sh -c "grep peer0 /etc/hosts"'
echo "=== warmup (validate status:200) ==="
W=$($SSH ubuntu@$H1 "sudo docker exec $PE1 peer0 peer chaincode invoke $INVW -c '{\"function\":\"CreateAsset\",\"Args\":[\"warm_t3b\",\"b\",\"1\",\"x\",\"1\"]}' --waitForEvent 2>&1 | grep -oE 'status:[0-9]+|Error[^\"]*' | head -1")
echo "  warmup: $W"
case "$W" in *200*) echo "  warmup OK, running sweep";; *) echo "  WARMUP_FAILED -> sweep would be invalid; aborting"; echo "ABORT"; exit 1;; esac
sleep 3
$SCP /mnt/d/fabric-d2/alg1/t3_remote.sh ubuntu@$H1:/tmp/t3_remote.sh
echo "=== concurrent throughput sweep (valid) ===" | tee "$OUT/results.txt"
for par in 1 4 8 12; do
  r=$($SSH ubuntu@$H1 "bash /tmp/t3_remote.sh $par 6 base 2>&1 | tail -1")
  echo "  $r" | tee -a "$OUT/results.txt"
done
echo "=== verify commits (asset count) ==="
$SSH ubuntu@$H1 "sudo docker exec $PE1 peer0 peer chaincode query $INVW --peerAddresses peer0.org1.example.com:7051 --tlsRootCertFiles /tmp/org1-ca.crt -c '{\"function\":\"GetAllAssets\",\"Args\":[]}' 2>&1 | grep -oE 'a_base_[0-9_]+' | wc -l" 2>&1 | tail -1
echo "XHOST_T3B_DONE"
