#!/usr/bin/env bash
# Clean low-load leadership-suppression measurement with a PROCESS-checked
# sidecar healer (the fix: a stale socket file is not a live advisor; every
# prior run fail-opened on dead sidecars). v4 orderer = tick-suppression +
# vote-grant predicate. Compares baseline [] vs BORA [3] over N forced
# elections per seed.
set -u
source /mnt/d/fabric-d2/alg1/sidecar_lib.sh
N="${N:-12}"
SEEDS="${SEEDS:-3}"
OUT=/mnt/d/fabric-d2/results/finalsupp_$(date +%Y%m%d-%H%M%S); mkdir -p "$OUT"
echo "label,seed,orderer3_wins,n,liveness" > "$OUT/results.csv"
: > "$OUT/elections.log"
RUN=/tmp/fs_heal.on; touch $RUN
( while [ -f $RUN ]; do ensure_all_sidecars; sleep 0.5; done ) & HP=$!
name(){ case $1 in 1)echo orderer.example.com;;2)echo orderer2.example.com;;3)echo orderer3.example.com;;4)echo orderer4.example.com;;5)echo orderer5.example.com;;esac; }
set_all(){ for o in "${ALL_ORD[@]}"; do docker exec "$o" sh -c "printf '%s' '{\"blacklist\":$1,\"seq\":1,\"fail_open\":false}' > /tmp/bora-advice.json" 2>/dev/null; done; }
leader_id(){ local b=-1 bid=0 id o t; for id in 1 2 3 4 5; do o=$(name $id); t=$(docker logs --tail 200 "$o" 2>&1 | grep -ao "became leader at term [0-9]*" | tail -1 | grep -ao "[0-9]*$"); [ -n "$t" ]&&[ "$t" -gt "$b" ]&&{ b=$t;bid=$id; }; done; echo $bid; }
phase(){ # $1=label $2=seq-id -> WINS LIVE
  WINS=0; LIVE=0; local k L LC NL
  for k in $(seq 1 "$N"); do
    L=$(leader_id); LC=$(name $L); [ -z "$LC" ]&&LC=orderer2.example.com
    docker restart "$LC" >/dev/null 2>&1; ensure_all_sidecars; sleep 12
    NL=$(leader_id); [ "$NL" = "3" ]&&WINS=$((WINS+1)); [ "$NL" != "0" ]&&LIVE=$((LIVE+1))
    echo "[$1] e$k: $L -> $NL" >> "$OUT/elections.log"
  done
}
ensure_all_sidecars
echo "=== final suppression: N=$N SEEDS=$SEEDS (process-checked healer) ===" | tee "$OUT/summary.txt"
for s in $(seq 1 "$SEEDS"); do
  echo "#### SEED $s ####" | tee -a "$OUT/summary.txt"
  set_all "[]"; sleep 2; phase "A_s$s"
  echo "  [A_s$s base] orderer3 $WINS/$N | live $LIVE/$N" | tee -a "$OUT/summary.txt"
  echo "A_base,$s,$WINS,$N,$LIVE" >> "$OUT/results.csv"
  set_all "[3]"; sleep 2; phase "B_s$s"
  echo "  [B_s$s BORA] orderer3 $WINS/$N | live $LIVE/$N" | tee -a "$OUT/summary.txt"
  echo "B_BORA,$s,$WINS,$N,$LIVE" >> "$OUT/results.csv"
done
set_all "[]"; rm -f $RUN; kill $HP 2>/dev/null || true
echo "FINAL_SUPP_DONE (results: $OUT)" | tee -a "$OUT/summary.txt"
cat "$OUT/results.csv" | tee -a "$OUT/summary.txt"
