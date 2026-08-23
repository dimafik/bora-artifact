#!/usr/bin/env bash
# Deploy the vote-reject orderer (v4) via rolling restart, then restart v3
# sidecars (which die when the orderer container restarts). Verify sockets.
set -e
BIN=/mnt/d/fabric-d2/results/orderer-bora-v4.bin
SIDE=/mnt/d/fabric-d2/results/bora-sidecar-v3.bin
ORDERERS=(orderer.example.com orderer2.example.com orderer3.example.com orderer4.example.com orderer5.example.com)

echo "[1] stage v4 binary..."
for o in "${ORDERERS[@]}"; do
  docker cp "$BIN" "$o:/usr/local/bin/orderer.bora4" >/dev/null
  docker exec "$o" chmod +x /usr/local/bin/orderer.bora4
done

echo "[2] atomic swap + rolling restart..."
for o in "${ORDERERS[@]}"; do
  docker exec "$o" sh -c 'mv /usr/local/bin/orderer.bora4 /usr/local/bin/orderer'
  docker restart "$o" >/dev/null
  echo "  $o restarted"; sleep 12
done

echo "[3] (re)start v3 sidecars..."
for o in "${ORDERERS[@]}"; do
  docker cp "$SIDE" "$o:/tmp/bora-sidecar" >/dev/null 2>&1 || true
  docker exec "$o" chmod +x /tmp/bora-sidecar
  docker exec "$o" sh -c 'pkill -f bora-sidecar 2>/dev/null; rm -f /var/run/raft-advisor.sock; printf "%s" "{\"blacklist\":[],\"seq\":1,\"fail_open\":false}" > /tmp/bora-advice.json'
  docker exec -d "$o" sh -c 'setsid /tmp/bora-sidecar >/tmp/bora-sidecar.log 2>&1 </dev/null'
done
sleep 3

echo "[4] verify sockets + cluster leader..."
ok=0
for o in "${ORDERERS[@]}"; do
  if docker exec "$o" sh -c 'test -S /var/run/raft-advisor.sock'; then echo "  $o SOCKET_OK"; ok=$((ok+1)); else echo "  $o MISS"; fi
done
echo "sidecars: $ok/5"
docker logs --tail 3 orderer.example.com 2>&1 | tail -3
echo "DEPLOY_BORA_V4_OK"
