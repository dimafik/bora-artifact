#!/usr/bin/env bash
# Cross-host bring-up, end to end, with every step verified.
#
# The pieces were scattered across eight scripts written at different times, and
# three of them fail in ways that look like something else:
#   nsweep/xhost_deploy    joins the ORDERERS and stops; its banner says
#                          "+ 2 peers" but no peer step follows
#   xhost_peer.sh          joins by IP, and the TLS certs carry FQDN SANs only,
#                          so the join fails with "bad certificate"
#   xhost_cc3.sh           passes OR('A','B') through ssh, where a second shell
#                          parses it and dies on the bare paren
# Each step below checks its own result and stops rather than handing the next
# step a half-built cluster.
#
# Usage: xhost_setup_all.sh
set -u
KEY=/tmp/bk.pem; chmod 600 "$KEY" 2>/dev/null
SSH="ssh -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=25 -o BatchMode=yes"
SCP="scp -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=25 -q"
PUB=(x 3.34.1.207 13.124.149.80 13.209.43.120 15.164.234.3 54.180.32.6)
PRIV=(x 172.31.39.233 172.31.44.2 172.31.37.115 172.31.46.160 172.31.39.145)
H6=43.201.115.162
N=5
D=/mnt/d/fabric-d2
TN=$D/fabric-samples/test-network
FVER=3.1.4
OUT=$D/results/xhost_setup_$(date +%Y%m%d-%H%M%S); mkdir -p "$OUT"
say(){ echo "[$(date +%H:%M:%S)] $*" | tee -a "$OUT/log.txt"; }
sshi(){ local i=$1; shift; $SSH ubuntu@${PUB[$i]} "$@"; }
PE1="-e CORE_PEER_ADDRESS=peer0.org1.example.com:7051 -e CORE_PEER_MSPCONFIGPATH=/etc/hyperledger/fabric/adminmsp"

say "===== 0. reachability ====="
for i in $(seq 1 $N); do
  r=$(sshi $i 'echo OK' 2>/dev/null); [ "$r" = OK ] || { say "  *** orderer$i unreachable"; exit 1; }
done
[ "$($SSH ubuntu@$H6 'echo OK' 2>/dev/null)" = OK ] || { say "  *** client host unreachable"; exit 1; }
say "  6/6 reachable"

say "===== 1. docker + images ====="
for i in $(seq 1 $N); do
  ( sshi $i "command -v docker >/dev/null || { sudo apt-get update -y >/dev/null 2>&1; sudo DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io >/dev/null 2>&1; sudo systemctl enable --now docker; }
     sudo docker pull hyperledger/fabric-orderer:$FVER >/dev/null 2>&1" ) &
done
( $SSH ubuntu@$H6 "command -v docker >/dev/null || { sudo apt-get update -y >/dev/null 2>&1; sudo DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io >/dev/null 2>&1; sudo systemctl enable --now docker; }
   sudo docker pull hyperledger/caliper:0.6.0 >/dev/null 2>&1" ) &
for i in 1 2; do
  ( sshi $i "for im in hyperledger/fabric-peer:$FVER hyperledger/fabric-ccenv:3.1 hyperledger/fabric-baseos:3.1; do sudo docker pull \$im >/dev/null 2>&1; done" ) &
done
wait
ok=0; for i in $(seq 1 $N); do [ -n "$(sshi $i "sudo docker images -q hyperledger/fabric-orderer:$FVER")" ] && ok=$((ok+1)); done
say "  orderer image on $ok/$N"; [ "$ok" = "$N" ] || exit 1

say "===== 2. crypto + genesis (fresh) ====="
bash "$D/alg1/xhost_build_genesis.sh" >>"$OUT/log.txt" 2>&1 || { say "  *** genesis failed"; exit 1; }
say "  genesis: $(stat -c %s "$D/results/xhost/mychannel.block") bytes"

say "===== 3. orderers ====="
for i in $(seq 1 $N); do sshi $i 'sudo docker rm -f orderer peer0 >/dev/null 2>&1; sudo rm -rf ~/ord ~/peer' >/dev/null 2>&1; done
bash "$D/alg1/xhost_deploy.sh" >>"$OUT/log.txt" 2>&1
up=0; for i in $(seq 1 $N); do [ "$(sshi $i 'sudo docker inspect -f "{{.State.Status}}" orderer 2>/dev/null')" = running ] && up=$((up+1)); done
say "  orderers running: $up/$N"; [ "$up" = "$N" ] || exit 1

say "===== 4. channel join ====="
bash "$D/alg1/xhost_join.sh" >>"$OUT/log.txt" 2>&1
j=$(grep -c "Status: 201" "$OUT/log.txt"); say "  joined (Status 201 count): $j"
[ "$j" -ge "$N" ] || { say "  *** not all orderers joined"; exit 1; }

say "===== 5. BORA binary + sidecars ====="
for i in $(seq 1 $N); do
  sshi $i 'sudo docker cp /home/ubuntu/ord/orderer-bora-v4.bin orderer:/usr/local/bin/orderer.b4 >/dev/null 2>&1 && sudo docker exec orderer chmod +x /usr/local/bin/orderer.b4 && sudo docker exec orderer sh -c "mv /usr/local/bin/orderer.b4 /usr/local/bin/orderer" && sudo docker restart orderer >/dev/null 2>&1' >/dev/null 2>&1
  sleep 8
done
sleep 5
for i in $(seq 1 $N); do
  sshi $i 'sudo docker cp /home/ubuntu/ord/bora-sidecar-v3.bin orderer:/tmp/bora-sidecar >/dev/null 2>&1; sudo docker exec orderer chmod +x /tmp/bora-sidecar; sudo docker exec orderer sh -c "pkill -f bora-sidecar 2>/dev/null; rm -f /var/run/raft-advisor.sock; printf %s \"{\\\"blacklist\\\":[],\\\"seq\\\":1,\\\"fail_open\\\":false}\" > /tmp/bora-advice.json"; sudo docker exec -d orderer sh -c "setsid /tmp/bora-sidecar >/tmp/bs.log 2>&1 </dev/null"' >/dev/null 2>&1
done
sleep 6
sc=0; for i in $(seq 1 $N); do sshi $i 'sudo docker exec orderer sh -c "cat /proc/[0-9]*/comm 2>/dev/null | grep -q ^bora-sidecar\$"' 2>/dev/null && sc=$((sc+1)); done
say "  sidecars: $sc/$N"; [ "$sc" = "$N" ] || exit 1

say "===== 6. peers ====="
bash "$D/alg1/xhost_peer.sh"  >>"$OUT/log.txt" 2>&1
bash "$D/alg1/xhost_peer2.sh" >>"$OUT/log.txt" 2>&1
# Both peers must resolve BOTH names: their own to loopback, the other to its
# private IP. The TLS certs have FQDN SANs and no IP SANs, so every address used
# from here on is a name.
for i in 1 2; do
  sshi $i "sudo docker exec peer0 bash -c 'grep -q peer0.org1 /etc/hosts || echo \"${PRIV[1]} peer0.org1.example.com\" >> /etc/hosts; grep -q peer0.org2 /etc/hosts || echo \"${PRIV[2]} peer0.org2.example.com\" >> /etc/hosts'" >/dev/null 2>&1
done
bash "$D/alg1/xhost_peer_join.sh" >>"$OUT/log.txt" 2>&1
# The verification must use the FQDN too. Checking with `docker exec peer0 peer
# channel list` and no CORE_PEER_ADDRESS makes the CLI dial the peer by IP, the
# TLS cert carries no IP SAN, and the list comes back EMPTY on a peer that is in
# fact joined -- which reported a false failure and stopped a good build.
for i in 1 2; do
  c=$(sshi $i "sudo docker exec -e CORE_PEER_ADDRESS=peer0.org$i.example.com:7051 peer0 peer channel list 2>/dev/null | grep -c mychannel")
  [ "${c:-0}" -ge 1 ] && say "  peer org$i joined" || { say "  *** peer org$i did NOT join"; exit 1; }
done
pv=$(sshi 1 "sudo docker exec peer0 peer version 2>/dev/null | grep -i '^ Version' | head -1")
say "  peer version:$pv"

say "===== 7. chaincode 'basic' (OR policy) ====="
export PATH=$HOME/go-install/bin:$D/fabric-samples/bin-linux/bin:$PATH
export FABRIC_CFG_PATH=$D/fabric-samples/config
( cd "$TN" && rm -f /tmp/basic.tar.gz && peer lifecycle chaincode package /tmp/basic.tar.gz \
    --path $D/fabric-samples/asset-transfer-basic/chaincode-go --lang golang --label basic_1 ) >>"$OUT/log.txt" 2>&1
[ -f /tmp/basic.tar.gz ] || { say "  *** packaging failed"; exit 1; }
for i in 1 2; do
  $SCP /tmp/basic.tar.gz ubuntu@${PUB[$i]}:/home/ubuntu/basic.tar.gz
  sshi $i 'sudo docker cp /home/ubuntu/basic.tar.gz peer0:/tmp/basic.tar.gz' >/dev/null 2>&1
done
ORDCA=$D/results/xhost/orderer-ca.pem
ORG1CA=$TN/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt
ORG2CA=$TN/organizations/peerOrganizations/org2.example.com/peers/peer0.org2.example.com/tls/ca.crt
for i in 1 2; do $SCP "$ORDCA" ubuntu@${PUB[$i]}:/home/ubuntu/ord-ca.crt; sshi $i 'sudo docker cp /home/ubuntu/ord-ca.crt peer0:/tmp/ord-ca.crt' >/dev/null 2>&1; done
$SCP "$ORG1CA" ubuntu@${PUB[1]}:/home/ubuntu/org1-ca.crt; $SCP "$ORG2CA" ubuntu@${PUB[1]}:/home/ubuntu/org2-ca.crt
sshi 1 'sudo docker cp /home/ubuntu/org1-ca.crt peer0:/tmp/org1-ca.crt; sudo docker cp /home/ubuntu/org2-ca.crt peer0:/tmp/org2-ca.crt' >/dev/null 2>&1
for i in 1 2; do
  sshi $i "sudo docker exec -e CORE_PEER_ADDRESS=peer0.org$i.example.com:7051 -e CORE_PEER_MSPCONFIGPATH=/etc/hyperledger/fabric/adminmsp peer0 peer lifecycle chaincode install /tmp/basic.tar.gz 2>&1 | tail -1" >>"$OUT/log.txt" 2>&1
done
bash "$D/alg1/xhost_cc_or.sh" >>"$OUT/log.txt" 2>&1
grep -q "Version: 1.0" "$OUT/log.txt" || { say "  *** chaincode not committed"; exit 1; }
say "  committed"

say "===== 8. caliper workspace on the client ====="
( cd $D && tar czf /tmp/calws.tgz caliper-workspace ) 2>/dev/null
( cd $TN && tar czf /tmp/crypto.tgz organizations ) 2>/dev/null
$SCP /tmp/calws.tgz /tmp/crypto.tgz ubuntu@$H6:/home/ubuntu/
$SSH ubuntu@$H6 'cd /home/ubuntu && rm -rf caliper-workspace organizations && tar xzf calws.tgz && tar xzf crypto.tgz && ls -d caliper-workspace organizations >/dev/null && echo ok' >/dev/null 2>&1
$SSH ubuntu@$H6 'test -f /home/ubuntu/caliper-workspace/workload/updateAsset.js' || { say "  *** workload missing on client"; exit 1; }
say "  workspace + crypto staged, bounded workload present"

h=$(sshi 1 "sudo docker exec $PE1 peer0 peer channel getinfo -c mychannel 2>/dev/null | grep -ao '\"height\":[0-9]*' | grep -ao '[0-9]*'")
say "===== ready: height=$h ====="
for i in $(seq 1 $N); do say "  orderer$i disk: $(sshi $i 'df -h / | tail -1 | awk "{print \$3\" used, \"\$5}"')"; done
