#!/usr/bin/env bash
# Robust task 2: minimal SSH. leader_id reads only orderer1+orderer2 logs (the
# cluster-wide "Raft leader changed" appears in every orderer; at most one of these
# two is the paused leader). No heal loop (pause/unpause does not kill the exec'd
# sidecar). Goal: many BORA forced elections (target orderer3) -> tighten Wilson.
set -u
cp /mnt/c/Users/jinu3/Bora_key1.pem /tmp/bk.pem 2>/dev/null; chmod 600 /tmp/bk.pem
SSH="ssh -i /tmp/bk.pem -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=15 -o ServerAliveInterval=5 -o ServerAliveCountMax=3"
PUB=(x 15.164.215.28 13.209.97.224 13.209.3.44 54.180.145.47 52.78.184.161)
N=5
sshi(){ local i=$1; shift; $SSH "ubuntu@${PUB[$i]}" "$@"; }
OUT=/mnt/d/fabric-d2/results/xhost_t2b_$(date +%H%M%S); mkdir -p "$OUT"

echo "=== unpause all + ensure sidecars ==="
for i in $(seq 1 $N); do sshi $i 'sudo docker unpause orderer 2>/dev/null; true' >/dev/null 2>&1; done
for i in $(seq 1 $N); do
  sshi $i 'sudo docker exec orderer sh -c "cat /proc/[0-9]*/comm 2>/dev/null | grep -q \"^bora-sidecar$\" || { rm -f /var/run/raft-advisor.sock; setsid /tmp/bora-sidecar >/tmp/bs.log 2>&1 </dev/null; }"' >/dev/null 2>&1
done
sleep 4
SOK=0; for i in $(seq 1 $N); do sshi $i 'sudo docker exec orderer sh -c "cat /proc/[0-9]*/comm 2>/dev/null | grep -q \"^bora-sidecar$\""' 2>/dev/null && SOK=$((SOK+1)); done
echo "  sidecars: $SOK/$N"
set_all(){ local i; for i in $(seq 1 $N); do sshi $i "sudo docker exec orderer sh -c \"printf '%s' '{\\\"blacklist\\\":$1,\\\"seq\\\":1,\\\"fail_open\\\":false}' > /tmp/bora-advice.json\"" 2>/dev/null; done; }
leader_id(){ local a b; a="$(sshi 1 'sudo docker logs --tail 300 orderer 2>&1 | grep -aE "Raft leader changed: [0-9]+ -> [0-9]+"')"; b="$(sshi 2 'sudo docker logs --tail 300 orderer 2>&1 | grep -aE "Raft leader changed: [0-9]+ -> [0-9]+"')"; printf '%s\n%s' "$a" "$b" | grep -aE 'Raft leader changed' | sort | tail -1 | grep -aoE '\-> [0-9]+' | grep -aoE '[0-9]+'; }

echo "=== BORA forced elections (target orderer3) ==="
set_all "[3]"; sleep 3
WINS=0; TOT=0; NE=12
for s in 1 2 3 4 5; do
  for k in $(seq 1 $NE); do
    L=$(leader_id); [ -z "$L" ]&&L=0; [ "$L" = 0 ]&&L=1
    sshi $L 'sudo docker pause orderer' >/dev/null 2>&1; sleep 11
    NL=$(leader_id); [ -z "$NL" ]&&NL=0
    sshi $L 'sudo docker unpause orderer' >/dev/null 2>&1; sleep 5
    TOT=$((TOT+1)); [ "$NL" = 3 ]&&WINS=$((WINS+1))
    echo "[s$s e$k] $L->$NL (o3 $WINS/$TOT)" >> "$OUT/elections.log"
  done
  echo "  seed $s: o3 $WINS/$TOT" | tee -a "$OUT/summary.txt"
done
set_all "[]"
echo "BORA_FORCED_TOTAL: o3 $WINS/$TOT" | tee -a "$OUT/summary.txt"
echo "XHOST_T2B_DONE"
