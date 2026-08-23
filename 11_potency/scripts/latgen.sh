#!/usr/bin/env bash
# Commit-latency distribution under a fixed offered load.
#
# The throughput measurement found no effect of autocorrelation, but throughput
# is a mean and burstiness classically shows up in the tail.  This records every
# transaction's end-to-end commit time so p50/p95/p99 can be compared, which is
# where a bursty delay would be expected to appear if it appears anywhere.
#
# Usage:  latgen.sh <seconds> [workers] [pace_seconds]
set -u

SECS="${1:?seconds}"
WORKERS="${2:-4}"
PACE="${3:-1.0}"
CH=mychannel
CC=basic
TN=/d/fabric-d2/fabric-samples/test-network
ORG=$TN/organizations
NAME=latgen-$$
RUNID="l$(date +%s)-$$"

ORDERER_CA=/etc/hyperledger/orderer-ca.pem
O1CA=/etc/hyperledger/org1-ca.pem
O2CA=/etc/hyperledger/org2-ca.pem

cleanup(){ docker rm -f "$NAME" >/dev/null 2>&1; }
trap cleanup EXIT INT TERM

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

MSYS_NO_PATHCONV=1 docker exec -d \
  -e SECS="$SECS" -e WORKERS="$WORKERS" -e CH="$CH" -e CC="$CC" \
  -e ORDERER_CA="$ORDERER_CA" -e O1CA="$O1CA" -e O2CA="$O2CA" \
  -e PACE="$PACE" -e RUNID="$RUNID" \
  "$NAME" sh /work/latgen_worker.sh

# MSYS_NO_PATHCONV on every docker exec below: Git Bash rewrites a bare /tmp/...
# argument to C:/Program Files/Git/tmp/..., which silently turns the completion
# probe into a never-true test and the sample read into an empty result.
for _ in $(seq 1 $((SECS + 180))); do
  MSYS_NO_PATHCONV=1 docker exec "$NAME" test -f /tmp/all.done 2>/dev/null && break
  sleep 1
done

MSYS_NO_PATHCONV=1 docker exec "$NAME" sh -c 'cat /tmp/lat.*.csv 2>/dev/null'
