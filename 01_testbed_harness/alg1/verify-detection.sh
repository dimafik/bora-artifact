#!/bin/bash
docker run -d --name pumba-verify -v /var/run/docker.sock:/var/run/docker.sock \
  gaiaadm/pumba:latest --interval 10m --log-level info \
  netem --tc-image gaiadocker/iproute2 --duration 90s \
  delay --time 200 orderer3.example.com 2>&1 | tail -1
sleep 8
echo "=== Run sidecar 30s with attack active ==="
timeout 30 python3 /mnt/d/fabric-d2/alg1/sidecar.py \
  --config /mnt/d/fabric-d2/alg1/alg1.yaml \
  --log /tmp/sidecar-verify.log 2>&1 | tail -3
echo "=== sidecar tail ==="
grep -E "TICK |YIELD|UNYIELD|ALR|fail-open" /tmp/sidecar-verify.log | tail -25
echo ""
echo "=== advice events count ==="
grep -c YIELD /tmp/sidecar-verify.log
docker rm -f pumba-verify 2>&1 | tail -1
for c in orderer.example.com orderer2.example.com orderer3.example.com orderer4.example.com orderer5.example.com; do
  docker unpause "$c" 2>/dev/null || true
done
