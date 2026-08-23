#!/usr/bin/env bash
KEY=/tmp/bk.pem; chmod 600 "$KEY" 2>/dev/null
SSH="ssh -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=15 -o BatchMode=yes"
PUB=(43.201.73.122 54.180.99.165 43.201.25.172 54.180.117.221 15.164.226.99)
HOSTN=(orderer orderer2 orderer3 orderer4 orderer5)
for i in 0 1 2 3 4; do
  ip=${PUB[$i]}
  st=$($SSH ubuntu@$ip 'sudo docker inspect -f "{{.State.Status}} restarts={{.RestartCount}}" orderer 2>/dev/null')
  echo "  ${HOSTN[$i]} ($ip): ${st:-NA}"
done
echo "=== orderer1 recent log (errors/leader) ==="
$SSH ubuntu@${PUB[0]} 'sudo docker logs --tail 25 orderer 2>&1 | grep -aiE "error|fail|panic|leader|became|active|TLS|started|complete" | tail -12'
