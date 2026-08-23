#!/usr/bin/env bash
# C step 4: drive application transactions through the cross-host network and measure
# throughput (tx/s) + commit latency. OR signature policy => single-org (Org1) endorse;
# transactions are ordered by the 5-host Raft cluster across real hosts.
set -u
KEY=/tmp/bk.pem; chmod 600 "$KEY" 2>/dev/null
SSH="ssh -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=25 -o BatchMode=yes"
H1=3.35.4.99
PE1="-e CORE_PEER_ADDRESS=peer0.org1.example.com:7051 -e CORE_PEER_MSPCONFIGPATH=/etc/hyperledger/fabric/adminmsp"
INV="--orderer orderer.example.com:7050 --tls --cafile /tmp/ord-ca.crt --ordererTLSHostnameOverride orderer.example.com -C mychannel -n basic --peerAddresses peer0.org1.example.com:7051 --tlsRootCertFiles /tmp/org1-ca.crt --peerAddresses peer0.org2.example.com:7051 --tlsRootCertFiles /tmp/org2-ca.crt"
N=${1:-30}; LABEL=${2:-baseline}
OUT=/mnt/d/fabric-d2/results/xhost_tput_$(date +%H%M%S); mkdir -p "$OUT"

echo "=== warmup InitLedger (waitForEvent) ==="
$SSH ubuntu@$H1 "sudo docker exec $PE1 peer0 peer chaincode invoke $INV -c '{\"function\":\"InitLedger\",\"Args\":[]}' --waitForEvent 2>&1 | grep -oE 'result: status:[0-9]+|Error.*' | head -1"
echo "=== query check ==="
$SSH ubuntu@$H1 "sudo docker exec $PE1 peer0 peer chaincode query $INV -c '{\"function\":\"GetAllAssets\",\"Args\":[]}' 2>&1 | head -c 200; echo"

echo "=== throughput: $N CreateAsset invokes ($LABEL) ==="
# Build a remote loop script to avoid per-call SSH overhead dominating the timing.
$SSH ubuntu@$H1 "cat > /tmp/tput.sh <<'EOS'
N=$N
start=\$(date +%s.%N)
ok=0
for k in \$(seq 1 \$N); do
  if sudo docker exec $PE1 peer0 peer chaincode invoke $INV -c \"{\\\"function\\\":\\\"CreateAsset\\\",\\\"Args\\\":[\\\"a\${k}_$LABEL\\\",\\\"blue\\\",\\\"5\\\",\\\"tom\\\",\\\"100\\\"]}\" >/dev/null 2>&1; then ok=\$((ok+1)); fi
done
end=\$(date +%s.%N)
el=\$(echo \"\$end - \$start\" | bc)
printf 'submitted=%d/%d elapsed=%.2fs tx/s=%.2f\n' \"\$ok\" \"\$N\" \"\$el\" \"\$(echo \"\$ok / \$el\" | bc -l)\"
EOS
bash /tmp/tput.sh"
echo "XHOST_TPUT_DONE ($LABEL)"
