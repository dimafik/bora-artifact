#!/usr/bin/env bash
# Task 2 (tighten Wilson): restart orderers, redeploy BORA sidecars, run many more
# BORA forced elections (target orderer3) on the physical 5-host cluster; expect 0 wins.
set -u
KEY=/tmp/bk.pem; chmod 600 "$KEY" 2>/dev/null
SSH="ssh -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=20 -o BatchMode=yes -o ServerAliveInterval=5 -o ServerAliveCountMax=3"
PUB=(x 15.164.215.28 13.209.97.224 13.209.3.44 54.180.145.47 52.78.184.161)  # 1-indexed
N=5
sshi(){ local i=$1; shift; $SSH ubuntu@${PUB[$i]} "$@"; }
OUT=/mnt/d/fabric-d2/results/xhost_t2_$(date +%H%M%S); mkdir -p "$OUT"

echo "=== restart orderers + redeploy sidecars ==="
for i in $(seq 1 $N); do sshi $i 'sudo docker start orderer >/dev/null 2>&1' ; done
sleep 12
for i in $(seq 1 $N); do
  sshi $i 'sudo docker cp /home/ubuntu/ord/bora-sidecar-v3.bin orderer:/tmp/bora-sidecar >/dev/null 2>&1; sudo docker exec orderer chmod +x /tmp/bora-sidecar; sudo docker exec orderer sh -c "pkill -f bora-sidecar 2>/dev/null; rm -f /var/run/raft-advisor.sock; printf %s \"{\\\"blacklist\\\":[],\\\"seq\\\":1,\\\"fail_open\\\":false}\" > /tmp/bora-advice.json"; sudo docker exec -d orderer sh -c "setsid /tmp/bora-sidecar >/tmp/bs.log 2>&1 </dev/null"' >/dev/null 2>&1
done
sleep 5
SOK=0; for i in $(seq 1 $N); do sshi $i 'sudo docker exec orderer sh -c "cat /proc/[0-9]*/comm 2>/dev/null | grep -q \"^bora-sidecar$\""' 2>/dev/null && SOK=$((SOK+1)); done
echo "  sidecars: $SOK/$N"

leader_id(){ local i all=""; for i in $(seq 1 $N); do all+="$(sshi $i 'sudo docker logs --tail 400 orderer 2>&1 | grep -aE "Raft leader changed: [0-9]+ -> [0-9]+"')"$'\n'; done; printf '%s' "$all" | grep -aE 'Raft leader changed' | sort | tail -1 | grep -aoE '\-> [0-9]+' | grep -aoE '[0-9]+'; }
set_all(){ local i; for i in $(seq 1 $N); do sshi $i "sudo docker exec orderer sh -c \"printf '%s' '{\\\"blacklist\\\":$1,\\\"seq\\\":1,\\\"fail_open\\\":false}' > /tmp/bora-advice.json\"" 2>/dev/null; done; }
heal(){ local i; for i in $(seq 1 $N); do sshi $i 'sudo docker exec -d orderer sh -c "cat /proc/[0-9]*/comm 2>/dev/null | grep -q \"^bora-sidecar\$\" || { rm -f /var/run/raft-advisor.sock; setsid /tmp/bora-sidecar >/tmp/bs.log 2>&1 </dev/null; }"' 2>/dev/null || true; done; }

RUN=/tmp/t2_heal; touch $RUN; ( while [ -f $RUN ]; do heal; sleep 3; done ) & HP=$!
echo "=== BORA forced elections, target orderer3 (expect 0 wins) ==="
set_all "[3]"; sleep 3
WINS=0; TOT=0; NE=12
for s in 1 2 3 4 5; do
  for k in $(seq 1 $NE); do
    L=$(leader_id); [ "$L" = 0 ]&&L=2
    sshi $L 'sudo docker pause orderer' >/dev/null 2>&1; sleep 11
    NL=$(leader_id)
    sshi $L 'sudo docker unpause orderer' >/dev/null 2>&1; sleep 5
    TOT=$((TOT+1)); [ "$NL" = 3 ]&&WINS=$((WINS+1))
    echo "[s$s e$k] $L->$NL  (o3 wins $WINS/$TOT)" >> "$OUT/elections.log"
  done
  echo "  seed $s done: o3 $WINS/$TOT" | tee -a "$OUT/summary.txt"
done
set_all "[]"; rm -f $RUN; kill $HP 2>/dev/null || true
echo "BORA_FORCED_TOTAL: o3 $WINS/$TOT" | tee -a "$OUT/summary.txt"
echo "XHOST_T2_DONE"
