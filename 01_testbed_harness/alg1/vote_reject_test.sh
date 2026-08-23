#!/usr/bin/env bash
# Measure orderer3 leadership-acquisition under the v4 (vote-reject) orderer.
# Healer keeps ALL sidecars up (voters must be live to reject orderer3's votes).
# Args: N (elections per condition). Compares baseline [] vs BORA [3].
set -u
N="${1:-15}"
OUT=/mnt/d/fabric-d2/results/votereject_$(date +%Y%m%d-%H%M%S); mkdir -p "$OUT"
ALL=(orderer.example.com orderer2.example.com orderer3.example.com orderer4.example.com orderer5.example.com)
RUN=/tmp/vr_heal.on; touch $RUN
( while [ -f $RUN ]; do
    for o in "${ALL[@]}"; do
      docker exec "$o" sh -c 'test -S /var/run/raft-advisor.sock || (setsid /tmp/bora-sidecar >/tmp/bora-sidecar.log 2>&1 </dev/null &)' 2>/dev/null
    done; sleep 0.6
  done ) & HP=$!
name_for_id(){ case $1 in 1)echo orderer.example.com;;2)echo orderer2.example.com;;3)echo orderer3.example.com;;4)echo orderer4.example.com;;5)echo orderer5.example.com;;*)echo "";;esac; }
set_all(){ for o in "${ALL[@]}"; do docker exec "$o" sh -c "printf '%s' '{\"blacklist\":$1,\"seq\":1,\"fail_open\":false}' > /tmp/bora-advice.json" 2>/dev/null; done; }
leader_id(){ local b=-1 bid=0 id o t; for id in 1 2 3 4 5; do o=$(name_for_id $id); t=$(docker logs --tail 200 "$o" 2>&1 | grep -ao "became leader at term [0-9]*" | tail -1 | grep -ao "[0-9]*$"); [ -n "$t" ]&&[ "$t" -gt "$b" ]&&{ b=$t;bid=$id; }; done; echo $bid; }
run(){ local w=0 live=0 k L LC NL prev=""; for k in $(seq 1 $1); do L=$(leader_id); LC=$(name_for_id $L); [ -z "$LC" ]&&LC=orderer2.example.com; docker restart "$LC" >/dev/null 2>&1; sleep 13; NL=$(leader_id); [ "$NL" = "3" ]&&w=$((w+1)); [ "$NL" != "0" ]&&live=$((live+1)); echo "[$2] e$k: $L -> $NL" >> "$OUT/elections.log"; done; echo "$w $live"; }

echo "label,orderer3_wins,n,liveness" > "$OUT/results.csv"
echo "=== v4 vote-reject test, N=$N ===" | tee "$OUT/summary.txt"
set_all "[3]"; sleep 2
read wB lB < <(run "$N" "B_BORA")
echo "BORA [3]:   orderer3 won $wB/$N | liveness $lB/$N" | tee -a "$OUT/summary.txt"
echo "B_BORA,$wB,$N,$lB" >> "$OUT/results.csv"
set_all "[]"; sleep 2
read wA lA < <(run "$N" "A_base")
echo "base []:    orderer3 won $wA/$N | liveness $lA/$N" | tee -a "$OUT/summary.txt"
echo "A_base,$wA,$N,$lA" >> "$OUT/results.csv"
set_all "[]"; rm -f $RUN; kill $HP 2>/dev/null || true
echo "VOTE_REJECT_TEST_DONE base=$wA/$N bora=$wB/$N (results: $OUT)" | tee -a "$OUT/summary.txt"
