#!/usr/bin/env bash
# Resume from STEP 3: robustly (re)start sidecars, verify sockets, then run LS2.
set -u
export PATH=/home/jinu337/go-install/bin:/mnt/d/fabric-d2/fabric-samples/bin-linux/bin:/usr/local/bin:/usr/bin:/bin
LOG=/mnt/d/fabric-d2/results/ls2_resume_$(date +%Y%m%d-%H%M%S).log
exec > >(tee "$LOG") 2>&1
echo "RESUME_LOG=$LOG"
ORDERERS=(orderer.example.com orderer2.example.com orderer3.example.com orderer4.example.com orderer5.example.com)

echo "================ STEP 3': start sidecars (setsid) ================"
for o in "${ORDERERS[@]}"; do
  docker exec "$o" sh -c 'pkill -f bora-sidecar 2>/dev/null; sleep 0.3; rm -f /var/run/raft-advisor.sock'
  docker exec "$o" sh -c 'printf "%s" "{\"blacklist\":[],\"seq\":1,\"fail_open\":false}" > /tmp/bora-advice.json'
  docker exec -d "$o" sh -c 'setsid /tmp/bora-sidecar >/tmp/bora-sidecar.log 2>&1 </dev/null'
  echo "  $o: sidecar launched"
done
sleep 4
ok=0
for o in "${ORDERERS[@]}"; do
  if docker exec "$o" sh -c 'test -S /var/run/raft-advisor.sock'; then
    echo "  $o: SOCKET_OK"; ok=$((ok+1))
  else
    echo "  $o: SOCKET_MISSING"; docker exec "$o" sh -c 'tail -4 /tmp/bora-sidecar.log 2>/dev/null' | sed 's/^/      /'
  fi
done
echo "sidecars up: $ok/5"
if [ "$ok" -lt 5 ]; then echo "RESUME_FAIL: not all sidecars up"; exit 1; fi

echo "================ STEP 4: LS2 experiment ================"
ATTACK_MS=500 N_ELECT=12 bash /mnt/d/fabric-d2/alg1/leader_scenario_v2.sh
echo "RESUME_LS2_DONE"
