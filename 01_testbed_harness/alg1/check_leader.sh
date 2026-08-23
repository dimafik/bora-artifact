#!/usr/bin/env bash
for i in 1 2 3 4 5 6 7; do
  h=orderer; [ "$i" -gt 1 ] && h="orderer$i"
  c="${h}.example.com"
  lead=$(docker logs --tail 400 "$c" 2>&1 | grep -aoE "became leader at term [0-9]+|Raft leader changed: [0-9]+ -> [0-9]+|is now the leader|leader=[0-9]+" | tail -1)
  st=$(docker inspect -f '{{.State.Status}}' "$c" 2>/dev/null)
  echo "orderer$i ($st): ${lead:-NO-LEADER-LOG}"
done
echo "--- any 'leader' mentions across cluster (sample) ---"
docker logs --tail 200 orderer.example.com 2>&1 | grep -aiE "leader|elect|campaign|term" | tail -4
