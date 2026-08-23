#!/usr/bin/env bash
# Cluster bring-up extracted verbatim from nsweep.sh (lines 1-73) so that
# x1_closedloop.sh and nsweep.sh build an identical N-orderer cluster.
# Re-extract with the extractor in the X1 design doc whenever nsweep.sh changes.
# N-orderer leadership-integrity sweep. Brings up an N-orderer BORA-patched Raft
# cluster from scratch, then measures the target orderer's (orderer3) forced-
# election win rate baseline [] vs BORA [3]. Usage: nsweep.sh <N> [seeds] [elections]
set -u
N="${1:?need N}"; SEEDS="${2:-2}"; NE="${3:-10}"
TN=/mnt/d/fabric-d2/fabric-samples/test-network
BIN=/mnt/d/fabric-d2/results/orderer-bora-v4.bin
SIDE=/mnt/d/fabric-d2/results/bora-sidecar-v3.bin
export PATH=/tmp/bin:/mnt/d/fabric-d2/fabric-samples/bin-linux/bin:/usr/local/bin:/usr/bin:/bin
cd "$TN"
host(){ [ "$1" = 1 ] && echo orderer || echo "orderer$1"; }
cont(){ echo "$(host $1).example.com"; }
# orderer1=7050, orderer2=8050, orderer_i=10050+1000*(i-3) for i>=3. 9050 is
# skipped because the peers and orderer CA own 9051/9052/9054. Numerically
# identical to the old 1..9 case table (kept in nsweep.sh.orig); extended to
# i<=21 for the X1 sweep.
gport(){ case $1 in 1)echo 7050;;2)echo 8050;;*)echo $(( 10050 + 1000 * ($1 - 3) ));;esac; }
aport(){ echo $(( $(gport $1) + 3 )); }
ORD=(); for i in $(seq 1 "$N"); do ORD+=("$(cont $i)"); done
OUT=/mnt/d/fabric-d2/results/nsweep_N${N}_$(date +%H%M%S); mkdir -p "$OUT"

echo "===== N=$N bring-up ====="
python3 /mnt/d/fabric-d2/alg1/gen_nnode.py "$N" | tail -1
COMPOSE_PROJECT_NAME=fabric docker compose -f "${N}node-raft.yaml" down --volumes >/dev/null 2>&1 || true
COMPOSE_PROJECT_NAME=fabric docker compose -f 5node-raft.yaml down --volumes >/dev/null 2>&1 || true
# belt-and-suspenders: nuke any surviving fabric_* orderer production volumes (stale CA in channel block)
for v in $(docker volume ls -q | grep -E "^fabric_orderer"); do docker volume rm "$v" >/dev/null 2>&1 || true; done
docker network rm fabric_test >/dev/null 2>&1 || true
rm -rf organizations/ordererOrganizations organizations/peerOrganizations channel-artifacts system-genesis-block
mkdir -p channel-artifacts
cryptogen generate --config=./organizations/cryptogen/crypto-config-orderer-${N}node.yaml --output=organizations 2>&1 | tail -1
cryptogen generate --config=./organizations/cryptogen/crypto-config-org1.yaml --output=organizations 2>&1 | tail -1
cryptogen generate --config=./organizations/cryptogen/crypto-config-org2.yaml --output=organizations 2>&1 | tail -1
echo "orderers: $(ls organizations/ordererOrganizations/example.com/orderers/ | wc -l)"
unset FABRIC_CFG_PATH
cp configtx/configtx.yaml /tmp/ctx.bak 2>/dev/null || true
cp configtx/configtx-${N}node.yaml configtx/configtx.yaml
configtxgen -profile ChannelUsingRaft -outputBlock ./channel-artifacts/mychannel.block -channelID mychannel -configPath ./configtx 2>&1 | grep -iE "writing|panic|error" | tail -2
cp /tmp/ctx.bak configtx/configtx.yaml 2>/dev/null || true
[ -f ./channel-artifacts/mychannel.block ] || { echo "GENESIS_FAIL N=$N"; exit 1; }
export FABRIC_CFG_PATH="$TN/../config"
COMPOSE_PROJECT_NAME=fabric docker compose -f "${N}node-raft.yaml" up -d 2>&1 | tail -2
sleep 12
echo "containers up: $(docker ps --filter name=orderer --format '{{.Names}}' | wc -l) orderers"

echo "===== channel join (${N} orderers + 2 peers) ====="
OCA=organizations/ordererOrganizations/example.com/orderers/orderer.example.com/msp/tlscacerts/tlsca.example.com-cert.pem
for i in $(seq 1 "$N"); do
  H=$(host $i); C=organizations/ordererOrganizations/example.com/orderers/${H}.example.com/tls
  osnadmin channel join --channelID mychannel --config-block ./channel-artifacts/mychannel.block \
    -o localhost:$(aport $i) --ca-file "$OCA" --client-cert "$C/server.crt" --client-key "$C/server.key" 2>&1 | grep -o "Status: 201\|already exists" | head -1 | sed "s/^/  orderer$i: /"
done
sleep 8
JOINED=0; for i in $(seq 1 "$N"); do
  H=$(host $i); C=organizations/ordererOrganizations/example.com/orderers/${H}.example.com/tls
  osnadmin channel list -o localhost:$(aport $i) --ca-file "$OCA" --client-cert "$C/server.crt" --client-key "$C/server.key" 2>&1 | grep -q mychannel && JOINED=$((JOINED+1))
done
echo "  orderers on channel: $JOINED/$N"

echo "===== deploy BORA v4 binary + sidecar to $N orderers ====="
for o in "${ORD[@]}"; do docker cp "$BIN" "$o:/usr/local/bin/orderer.b4" >/dev/null && docker exec "$o" chmod +x /usr/local/bin/orderer.b4; done
for o in "${ORD[@]}"; do docker exec "$o" sh -c 'mv /usr/local/bin/orderer.b4 /usr/local/bin/orderer'; docker restart "$o" >/dev/null; sleep 10; done
for o in "${ORD[@]}"; do
  docker cp "$SIDE" "$o:/tmp/bora-sidecar" >/dev/null 2>&1 || true
  docker exec "$o" chmod +x /tmp/bora-sidecar
  docker exec "$o" sh -c 'pkill -f bora-sidecar 2>/dev/null; rm -f /var/run/raft-advisor.sock; printf "%s" "{\"blacklist\":[],\"seq\":1,\"fail_open\":false}" > /tmp/bora-advice.json'
  docker exec -d "$o" sh -c 'setsid /tmp/bora-sidecar >/tmp/bora-sidecar.log 2>&1 </dev/null'
done
sleep 4
SOK=0; for o in "${ORD[@]}"; do docker exec "$o" sh -c 'test -S /var/run/raft-advisor.sock' && SOK=$((SOK+1)); done
echo "  sidecars: $SOK/$N"

