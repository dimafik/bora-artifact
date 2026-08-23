#!/usr/bin/env bash
# Cross-host: deploy BORA v4 binary + sidecar to all 5 orderers, then run the
# forced-election exclusion test (target=orderer3, baseline [] vs BORA [3]) by
# pausing the current leader's container (over SSH) on its own physical host.
set -u
KEY=/tmp/bk.pem; chmod 600 "$KEY" 2>/dev/null
SSH="ssh -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=15 -o BatchMode=yes"
PUB=(x 43.201.73.122 54.180.99.165 43.201.25.172 54.180.117.221 15.164.226.99)   # 1-indexed
N=5
sshi(){ local i=$1; shift; $SSH ubuntu@${PUB[$i]} "$@"; }
OUT=/mnt/d/fabric-d2/results/xhost_election_$(date +%H%M%S); mkdir -p "$OUT"

leader_id(){ local i o all=""; for i in $(seq 1 $N); do o=$(sshi $i 'sudo docker logs --tail 400 orderer 2>&1 | grep -aE "Raft leader changed: [0-9]+ -> [0-9]+"'); all+="$o"$'\n'; done; local y; y=$(printf '%s' "$all" | grep -aE 'Raft leader changed' | sort | tail -1 | grep -aoE '\-> [0-9]+' | grep -aoE '[0-9]+'); echo "${y:-0}"; }
sidecars_up(){ local i n=0; for i in $(seq 1 $N); do sshi $i 'sudo docker exec orderer sh -c "cat /proc/[0-9]*/comm 2>/dev/null | grep -q \"^bora-sidecar$\""' 2>/dev/null && n=$((n+1)); done; echo $n; }
set_all(){ local i; for i in $(seq 1 $N); do sshi $i "sudo docker exec orderer sh -c \"printf '%s' '{\\\"blacklist\\\":$1,\\\"seq\\\":1,\\\"fail_open\\\":false}' > /tmp/bora-advice.json\"" 2>/dev/null; done; }
heal(){ local i; for i in $(seq 1 $N); do sshi $i 'sudo docker exec -d orderer sh -c "cat /proc/[0-9]*/comm 2>/dev/null | grep -q \"^bora-sidecar\$\" || { rm -f /var/run/raft-advisor.sock; setsid /tmp/bora-sidecar >/tmp/bs.log 2>&1 </dev/null; }"' 2>/dev/null || true; done; }

echo "=== deploy BORA v4 binary + sidecar to 5 hosts ==="
for i in $(seq 1 $N); do
  sshi $i 'sudo docker cp /home/ubuntu/ord/orderer-bora-v4.bin orderer:/usr/local/bin/orderer.b4 >/dev/null 2>&1 && sudo docker exec orderer chmod +x /usr/local/bin/orderer.b4 && sudo docker exec orderer sh -c "mv /usr/local/bin/orderer.b4 /usr/local/bin/orderer" && sudo docker restart orderer >/dev/null 2>&1 && echo ok' >/dev/null 2>&1
  sleep 8
  st=$(sshi $i 'sudo docker inspect -f "{{.State.Status}} r={{.RestartCount}}" orderer 2>/dev/null')
  echo "  orderer$i after BORA swap: $st"
done
sleep 6
echo "=== deploy sidecars ==="
for i in $(seq 1 $N); do
  sshi $i 'sudo docker cp /home/ubuntu/ord/bora-sidecar-v3.bin orderer:/tmp/bora-sidecar >/dev/null 2>&1; sudo docker exec orderer chmod +x /tmp/bora-sidecar; sudo docker exec orderer sh -c "pkill -f bora-sidecar 2>/dev/null; rm -f /var/run/raft-advisor.sock; printf %s \"{\\\"blacklist\\\":[],\\\"seq\\\":1,\\\"fail_open\\\":false}\" > /tmp/bora-advice.json"; sudo docker exec -d orderer sh -c "setsid /tmp/bora-sidecar >/tmp/bs.log 2>&1 </dev/null"' >/dev/null 2>&1
done
sleep 5; echo "  sidecars up: $(sidecars_up)/$N"
echo "  current leader: $(leader_id)"

RUN=/tmp/xh_heal; touch $RUN; ( while [ -f $RUN ]; do heal; sleep 3; done ) & HP=$!
echo "label,N,seed,o3_wins,elec,live" > "$OUT/results.csv"
phase(){ WINS=0; LIVE=0; local k L NL; for k in $(seq 1 "$2"); do
    L=$(leader_id); [ "$L" = 0 ]&&L=2
    sshi $L 'sudo docker pause orderer' >/dev/null 2>&1; sleep 11
    NL=$(leader_id)
    sshi $L 'sudo docker unpause orderer' >/dev/null 2>&1; sleep 5
    [ "$NL" = 3 ]&&WINS=$((WINS+1)); [ "$NL" != 0 ]&&[ "$NL" != "$L" ]&&LIVE=$((LIVE+1))
    echo "[$1] e$k: $L->$NL" >> "$OUT/elections.log"; done; }

NE=8
for s in 1 2; do
  set_all "[]"; sleep 2; phase "base_s$s" $NE
  echo "  XHOST N=5 base s$s: o3 $WINS/$NE live $LIVE/$NE" | tee -a "$OUT/summary.txt"
  echo "base,5,$s,$WINS,$NE,$LIVE" >> "$OUT/results.csv"
  set_all "[3]"; sleep 2; phase "bora_s$s" $NE
  echo "  XHOST N=5 BORA s$s: o3 $WINS/$NE live $LIVE/$NE" | tee -a "$OUT/summary.txt"
  echo "bora,5,$s,$WINS,$NE,$LIVE" >> "$OUT/results.csv"
done
set_all "[]"; rm -f $RUN; kill $HP 2>/dev/null || true
echo "XHOST_ELECTION_DONE"; cat "$OUT/results.csv"
