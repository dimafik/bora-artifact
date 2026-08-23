#!/usr/bin/env bash
# Constant-load generator and throughput meter, without Caliper.
#
# Caliper is not installed in this workspace and installing it pulls a large npm
# tree that has broken here before.  It is also more than this measurement
# needs: the question is not what peak throughput the cluster can reach, it is
# whether one delay pattern commits less than another under the *same* offered
# load.  A fixed number of concurrent invoke loops gives that comparison, and
# the metric that matters -- committed blocks -- is read from the ledger rather
# than from the client, so a client-side timeout cannot be mistaken for a
# consensus failure the way it was in the NE26 campaign.
#
# Usage:  loadgen.sh <seconds> [workers] [pace_seconds]
set -u

SECS="${1:?seconds}"
WORKERS="${2:-4}"
PACE="${3:-1.0}"          # seconds between invokes per worker -> WORKERS/PACE tx/s offered
CH=mychannel
CC=basic
TN=/d/fabric-d2/fabric-samples/test-network
ORG=$TN/organizations
NAME=loadgen-$$
# Unique per invocation.  Asset keys derived from the container shell PID
# repeated across runs, so a second run recreated the first run's assets and
# every CreateAsset was rejected -- indistinguishable, in the results, from the
# cluster refusing the load.
RUNID="r$(date +%s)-$$"

ORDERER_CA=/etc/hyperledger/orderer-ca.pem
O1CA=/etc/hyperledger/org1-ca.pem
O2CA=/etc/hyperledger/org2-ca.pem

cleanup(){ docker rm -f "$NAME" >/dev/null 2>&1; }
trap cleanup EXIT INT TERM

# One long-lived container: starting a peer process per transaction would make
# client startup, not the ordering service, the thing being measured.
MSYS_NO_PATHCONV=1 docker run -d --name "$NAME" --network fabric_test \
  -v "$ORG/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp":/etc/hyperledger/admin1 \
  -v "$ORG/ordererOrganizations/example.com/orderers/orderer.example.com/msp/tlscacerts/tlsca.example.com-cert.pem":$ORDERER_CA \
  -v "$ORG/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt":$O1CA \
  -v "$ORG/peerOrganizations/org2.example.com/peers/peer0.org2.example.com/tls/ca.crt":$O2CA \
  -e CORE_PEER_TLS_ENABLED=true \
  -e CORE_PEER_LOCALMSPID=Org1MSP \
  -e CORE_PEER_MSPCONFIGPATH=/etc/hyperledger/admin1 \
  -e CORE_PEER_ADDRESS=peer0.org1.example.com:7051 \
  -e CORE_PEER_TLS_ROOTCERT_FILE=$O1CA \
  -v /d/fabric-d2/alg1:/work \
  --entrypoint sh hyperledger/fabric-tools:2.5 -c "sleep $((SECS * 3 + 600))" >/dev/null

sleep 2

# The first version read the closing height through the load container and gave
# it a lifetime of SECS+120.  Runs took SECS+200, so the container was gone by
# the time the measurement ran: every condition reported an empty end height and
# a negative block count, while the ledger had in fact advanced 765 blocks.  The
# meter must not share a lifetime with the thing it measures, so heights now come
# from a separate short-lived container.
height(){ # committed blocks, read from the ledger
  MSYS_NO_PATHCONV=1 docker run --rm --network fabric_test \
    -v "$ORG/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp":/etc/hyperledger/admin1 \
    -v "$ORG/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt":$O1CA \
    -e CORE_PEER_TLS_ENABLED=true -e CORE_PEER_LOCALMSPID=Org1MSP \
    -e CORE_PEER_MSPCONFIGPATH=/etc/hyperledger/admin1 \
    -e CORE_PEER_ADDRESS=peer0.org1.example.com:7051 \
    -e CORE_PEER_TLS_ROOTCERT_FILE=$O1CA \
    hyperledger/fabric-tools:2.5 peer channel getinfo -c "$CH" 2>/dev/null \
    | grep -ao '"height":[0-9]*' | grep -ao '[0-9]*$'
}

H0=$(height); T0=$(date +%s)
[ -n "${H0:-}" ] || { echo "NO_CHANNEL -- run restore_channel.sh first"; exit 1; }

# invoke loops inside the container; each writes a success counter it owns
MSYS_NO_PATHCONV=1 docker exec -d \
  -e SECS="$SECS" -e WORKERS="$WORKERS" -e CH="$CH" -e CC="$CC" \
  -e ORDERER_CA="$ORDERER_CA" -e O1CA="$O1CA" -e O2CA="$O2CA" -e PACE="$PACE" \
  -e RUNID="$RUNID" \
  "$NAME" sh /work/loadgen_worker.sh

# Wait for the workers.  MSYS_NO_PATHCONV matters on every one of these: Git
# Bash rewrites a bare /tmp/... argument to C:/Program Files/Git/tmp/..., so
# without it the completion probe never sees the flag and the loop runs its full
# timeout, while the counter reads return nothing.  The run then reports zero
# transactions over an inflated duration -- both wrong, neither raising an error.
for _ in $(seq 1 $((SECS + 90))); do
  MSYS_NO_PATHCONV=1 docker exec "$NAME" test -f /tmp/all.done 2>/dev/null && break
  sleep 1
done

T1=$(date +%s); H1=$(height)
OK=0; TRIED=0
for w in $(seq 1 "$WORKERS"); do
  line=$(MSYS_NO_PATHCONV=1 docker exec "$NAME" cat "/tmp/w$w.done" 2>/dev/null)
  set -- ${line:-0 0}
  OK=$((OK + ${1:-0})); TRIED=$((TRIED + ${2:-0}))
done

SEC=$((T1 - T0)); BLK=$((H1 - H0))
awk -v ok="$OK" -v tr="$TRIED" -v b="$BLK" -v s="$SEC" -v h0="$H0" -v h1="$H1" -v w="$WORKERS" \
  'BEGIN{printf "workers=%d seconds=%d height %s->%s blocks=%d blocks_per_s=%.4f tx_ok=%d tx_tried=%d tx_per_s=%.3f\n",
         w, s, h0, h1, b, (s>0?b/s:0), ok, tr, (s>0?ok/s:0)}'
