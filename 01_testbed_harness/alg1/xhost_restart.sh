#!/usr/bin/env bash
# Bring the 5-host cluster back after an instance stop/start: containers persist on
# EBS (exited state); docker start re-runs them. Private IPs are unchanged so the
# --add-host wiring and channel data remain valid. New public IPs for SSH only.
set -u
KEY=/tmp/bk.pem; chmod 600 "$KEY" 2>/dev/null
SSH="ssh -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=15 -o BatchMode=yes"
PUB=(3.35.4.99 15.165.203.234 52.78.62.61 13.209.64.57 54.180.100.244)
HOSTN=(orderer orderer2 orderer3 orderer4 orderer5)
echo "=== docker start orderer on each host ==="
for i in 0 1 2 3 4; do
  st=$($SSH ubuntu@${PUB[$i]} 'sudo docker start orderer >/dev/null 2>&1; sudo docker inspect -f "{{.State.Status}}" orderer 2>/dev/null')
  echo "  ${HOSTN[$i]} (${PUB[$i]}): ${st:-NA}"
done
sleep 14
echo "=== leader / channel after restart ==="
all=""
for i in 0 1 2 3 4; do
  o=$($SSH ubuntu@${PUB[$i]} 'sudo docker logs --tail 60 orderer 2>&1 | grep -aE "Raft leader changed: [0-9]+ -> [0-9]+"')
  all+="$o"$'\n'
done
printf '%s' "$all" | grep -aE 'Raft leader changed' | sort | tail -1
echo "  sidecars: "
for i in 0 1 2 3 4; do
  s=$($SSH ubuntu@${PUB[$i]} 'sudo docker exec orderer sh -c "cat /proc/[0-9]*/comm 2>/dev/null | grep -c \"^bora-sidecar$\""' 2>/dev/null)
  echo "    ${HOSTN[$i]}: sidecar=${s:-0}"
done
echo "XHOST_RESTART_DONE"
