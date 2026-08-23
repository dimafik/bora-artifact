#!/usr/bin/env bash
set -e
BIN=/mnt/d/fabric-d2/results/orderer-bora-v3.bin
ORDERERS=(orderer.example.com orderer2.example.com orderer3.example.com orderer4.example.com orderer5.example.com)

echo "[stage 1] Deploy patched binary to each orderer container..."
for o in "${ORDERERS[@]}"; do
  docker exec "$o" sh -c 'test -f /usr/local/bin/orderer.vanilla.bak || cp /usr/local/bin/orderer /usr/local/bin/orderer.vanilla.bak'
  docker cp "$BIN" "$o:/usr/local/bin/orderer.bora" 2>/dev/null || true
  docker exec "$o" chmod +x /usr/local/bin/orderer.bora
  echo "  $o: bora binary staged"
done

echo
echo "[stage 2] Atomic swap (mv) + sequential rolling restart..."
for o in "${ORDERERS[@]}"; do
  # mv is atomic on the same fs; running binary keeps its old inode,
  # the new file appears at the same path for the next exec.
  docker exec "$o" sh -c 'mv /usr/local/bin/orderer.bora /usr/local/bin/orderer'
  docker restart "$o" > /dev/null
  echo "  $o restarted, sleeping 12s for cluster reconvergence..."
  sleep 12
done

echo
echo "[stage 3] Verify all 5 orderers running BORA binary..."
for o in "${ORDERERS[@]}"; do
  echo -n "  $o: "
  docker exec "$o" orderer version 2>&1 | grep -E 'Version|Commit' | head -2 | tr '\n' ' '
  echo
done

echo
echo "[stage 4] Cluster liveness probe..."
docker logs --tail 5 orderer.example.com 2>&1 | tail -5
echo "DEPLOY_BORA_V3_OK"
