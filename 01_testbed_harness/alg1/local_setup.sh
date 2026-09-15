#!/usr/bin/env bash
# Bring the single-host testbed to a state a CLIENT can drive: N orderers on the
# channel, both peers joined, chaincode 'basic' committed, anchor peers set.
#
# nsweep_bringup.sh stops after the orderers, because the leadership experiments
# it serves never needed a peer -- its own banner says "N orderers + 2 peers" but
# no peer step follows it. Every throughput measurement on this rig needs the
# three steps below as well, and each of them failed in a way that looked like
# something else the first time:
#   peer join      the MSP baked into a peer container is the PEER identity and
#                  lacks OU=ADMIN, so JoinChain fails until the admin MSP is
#                  copied in and pointed at explicitly
#   chaincode      caliper's workload calls contract 'basic'; without it every
#                  transaction fails and caliper reports SEND rate as throughput
#   anchor peers   the connection profile uses discover:true, and discovery
#                  cannot satisfy a majority-of-orgs policy without anchors:
#                  "no combination of peers can be derived which satisfy the
#                  endorsement policy", with the ledger sitting still
#
# Usage: local_setup.sh [N]
set -u
N="${1:-5}"
D=/mnt/d/fabric-d2
TN=$D/fabric-samples/test-network
export PATH=/tmp/bin:$D/fabric-samples/bin-linux/bin:/usr/local/bin:/usr/bin:/bin
OUT=$D/results/local_setup_$(date +%Y%m%d-%H%M%S); mkdir -p "$OUT"
say(){ echo "[$(date +%H:%M:%S)] $*" | tee -a "$OUT/log.txt"; }

say "===== bring-up N=$N ====="
bash "$D/alg1/nsweep_bringup.sh" "$N" >>"$OUT/log.txt" 2>&1 || { say "bring-up FAILED"; exit 1; }
say "  orderers up: $(docker ps -q -f name=orderer | wc -l)"

say "===== join peers ====="
for spec in \
 "peer0.org1.example.com Org1MSP org1.example.com peer0.org1.example.com:7051" \
 "peer0.org2.example.com Org2MSP org2.example.com peer0.org2.example.com:9051"; do
  set -- $spec
  PC="$1"; MSPID="$2"; ORGDOM="$3"; ADDR="$4"
  docker cp "$TN/channel-artifacts/mychannel.block" "$PC:/tmp/mychannel.block" >/dev/null 2>&1
  docker cp "$TN/organizations/peerOrganizations/$ORGDOM/users/Admin@$ORGDOM/msp" \
            "$PC:/tmp/adminmsp" >/dev/null 2>&1
  docker exec -e CORE_PEER_LOCALMSPID="$MSPID" -e CORE_PEER_MSPCONFIGPATH=/tmp/adminmsp \
              -e CORE_PEER_TLS_ROOTCERT_FILE=/etc/hyperledger/fabric/tls/ca.crt \
              -e CORE_PEER_ADDRESS="$ADDR" \
    "$PC" peer channel join -b /tmp/mychannel.block >>"$OUT/log.txt" 2>&1
done
sleep 8
for p in peer0.org1.example.com peer0.org2.example.com; do
  docker exec "$p" peer channel list 2>/dev/null | grep -q mychannel \
    && say "  $p joined" || { say "  *** $p did NOT join"; exit 1; }
done

say "===== anchor peers ====="
bash "$D/alg1/_set_anchors.sh" >>"$OUT/log.txt" 2>&1
grep -q "ANCHOR_OK org2" "$OUT/log.txt" || { say "  *** anchors not set"; exit 1; }
say "  anchors set"

say "===== chaincode 'basic' ====="
export PATH="$HOME/go-install/bin:$PATH"
command -v go >/dev/null || { say "  *** go not found"; exit 1; }
cc_ok(){ docker exec -e CORE_PEER_LOCALMSPID=Org1MSP -e CORE_PEER_MSPCONFIGPATH=/tmp/adminmsp \
  peer0.org1.example.com peer lifecycle chaincode querycommitted \
  --channelID mychannel --name basic 2>/dev/null | grep -q "Version: 1.0"; }
if cc_ok; then say "  already committed"; else
  ( cd "$TN" && ./network.sh deployCC -c mychannel -ccn basic \
      -ccp ../asset-transfer-basic/chaincode-go -ccl go ) >>"$OUT/log.txt" 2>&1
  cc_ok || { say "  *** deploy failed, see $OUT/log.txt"; exit 1; }
  say "  deployed"
fi

h=$(docker exec -e CORE_PEER_LOCALMSPID=Org1MSP -e CORE_PEER_MSPCONFIGPATH=/tmp/adminmsp \
  peer0.org1.example.com peer channel getinfo -c mychannel 2>/dev/null \
  | grep -ao '"height":[0-9]*' | grep -ao '[0-9]*')
say "===== ready: height=$h, $(docker ps -q -f name=orderer | wc -l) orderers ====="
