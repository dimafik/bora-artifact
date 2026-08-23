#!/usr/bin/env bash
# Check live advice + socket + sidecar liveness across all N=7 orderers
for i in 1 2 3 4 5 6 7; do
  h=orderer
  if [ "$i" -gt 1 ]; then h="orderer$i"; fi
  c="$h.example.com"
  st=$(docker inspect -f '{{.State.Status}}' "$c" 2>/dev/null)
  adv=$(docker exec "$c" sh -c 'cat /tmp/bora-advice.json 2>/dev/null' 2>/dev/null | tr -d '\n ' | cut -c1-48)
  sock=$(docker exec "$c" sh -c 'test -S /var/run/raft-advisor.sock && echo SOCK || echo no-sock' 2>/dev/null)
  live=$(docker exec "$c" sh -c 'cat /proc/[0-9]*/comm 2>/dev/null | grep -q "^bora-sidecar$" && echo SIDECAR-UP || echo SIDECAR-DOWN' 2>/dev/null)
  echo "orderer$i ($st): adv=${adv:-ERR} $sock $live"
done
echo "--- current leader ---"
all=""
for i in 1 2 3 4 5 6 7; do
  h=orderer
  if [ "$i" -gt 1 ]; then h="orderer$i"; fi
  all+="$(docker logs --tail 200 "$h.example.com" 2>&1 | grep -aE 'Raft leader changed: [0-9]+ -> [0-9]+')"$'\n'
done
printf '%s' "$all" | grep -aE 'Raft leader changed' | sort | tail -1
