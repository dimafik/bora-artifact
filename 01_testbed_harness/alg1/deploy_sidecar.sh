#!/usr/bin/env bash
# Deploy bora-sidecar binary into each orderer container and start it.
set -e
BIN=/mnt/d/fabric-d2/results/bora-sidecar.bin
ORDERERS=(orderer.example.com orderer2.example.com orderer3.example.com orderer4.example.com orderer5.example.com)

# Default advice: empty B_t, fail-open false (vanilla behavior).
DEFAULT_ADVICE='{"blacklist":[],"seq":1,"fail_open":false}'

echo "[1/3] Copy sidecar binary to each orderer..."
for o in "${ORDERERS[@]}"; do
  docker cp "$BIN" "$o:/tmp/bora-sidecar" 2>/dev/null || true
  docker exec "$o" chmod +x /tmp/bora-sidecar
  # Seed initial advice file (vanilla behaviour).
  docker exec "$o" sh -c "echo '$DEFAULT_ADVICE' > /tmp/bora-advice.json"
  echo "  $o ready"
done

echo
echo "[2/3] Start sidecar in each orderer (background)..."
for o in "${ORDERERS[@]}"; do
  # Kill any prior instance
  docker exec "$o" sh -c "pkill -f bora-sidecar 2>/dev/null; sleep 0.5; rm -f /var/run/raft-advisor.sock"
  # Start fresh in background, redirect logs
  docker exec -d "$o" sh -c '/tmp/bora-sidecar > /tmp/bora-sidecar.log 2>&1'
  sleep 1
  if docker exec "$o" sh -c 'test -S /var/run/raft-advisor.sock'; then
    echo "  $o: UDS socket up at /var/run/raft-advisor.sock"
  else
    echo "  $o: WARN socket not present, log tail:"
    docker exec "$o" cat /tmp/bora-sidecar.log 2>&1 | sed 's/^/    /'
  fi
done

echo
echo "[3/3] Verify advice end-to-end (orderer1 -> sidecar UDS round-trip)..."
docker exec orderer.example.com sh -c '
  if command -v nc >/dev/null 2>&1; then
    echo "  via nc:"
    nc -U /var/run/raft-advisor.sock | head -1
  else
    # Use the orderer binary itself? No, fall back to dd reading 1 byte.
    echo "  nc unavailable; reading first 128 bytes via dd:"
    dd if=/var/run/raft-advisor.sock bs=128 count=1 2>/dev/null || true
  fi'
echo
echo "DEPLOY_SIDECAR_OK"
