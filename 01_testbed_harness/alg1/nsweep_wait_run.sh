#!/usr/bin/env bash
# Wait for Docker to be ready, clean any stale fabric state, then run nsweep N.
N="${1:-7}"; SEEDS="${2:-2}"; NE="${3:-10}"
echo "waiting for docker..."
for i in $(seq 1 60); do docker ps >/dev/null 2>&1 && break; sleep 5; done
docker ps >/dev/null 2>&1 || { echo "DOCKER_NOT_READY"; exit 1; }
echo "docker ready ($(docker ps -q | wc -l) containers)"
# clean any leftover fabric containers/network from the failed run
docker rm -f $(docker ps -aq --filter name=orderer --filter name=peer0 2>/dev/null) >/dev/null 2>&1 || true
docker network rm fabric_test >/dev/null 2>&1 || true
sleep 2
bash /mnt/d/fabric-d2/alg1/nsweep.sh "$N" "$SEEDS" "$NE"
