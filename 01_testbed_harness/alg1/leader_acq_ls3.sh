#!/usr/bin/env bash
# ============================================================================
# LS3: Adversarial leadership-acquisition under SUSTAINED BORA advice.
#
# Insight from LS2: a network-DELAYED node cannot win elections (its votes are
# delayed), so a delay attack already excludes it from leadership and BORA is
# redundant in that regime (-> throughput-neutral, the honest paper result).
# BORA's leadership value is therefore against a HEALTHY adversary that CAN
# win elections but should be denied leadership. This experiment measures that.
#
# Target = orderer3 (healthy, no delay). Over N forced elections per seed:
#   A (no BORA, blacklist=[]):  orderer3 wins ~1/(N-1) of elections.
#   B (BORA, blacklist=[3] SUSTAINED via refresher): orderer3 wins ~0.
# Liveness: every forced election must still elect SOME leader.
#
# Fix vs the old EXP-A: advice is refreshed faster than the 500ms Raft tick so
# orderer3's election-tick suppression is continuous (the seq-gate otherwise
# made it last a single tick -> the weak 32%->18% in the prior campaign).
# ============================================================================
set -u
N_ELECT="${N_ELECT:-12}"
SEEDS="${SEEDS:-3}"
OUT=/mnt/d/fabric-d2/results/leaderacq_$(date +%Y%m%d-%H%M%S); mkdir -p "$OUT"
ORDERERS=(orderer.example.com orderer2.example.com orderer3.example.com orderer4.example.com orderer5.example.com)
BL_FILE="$OUT/blacklist.json"; echo "[]" > "$BL_FILE"
SEQ_FILE="$OUT/seq.txt"; echo 3000 > "$SEQ_FILE"
RUN_FLAG="$OUT/refresh.on"; touch "$RUN_FLAG"

name_for_id(){ case $1 in 1) echo orderer.example.com;; 2) echo orderer2.example.com;; 3) echo orderer3.example.com;; 4) echo orderer4.example.com;; 5) echo orderer5.example.com;; *) echo "";; esac; }

# robust leader detection: node with the highest "became leader at term T"
leader_id(){
  local best_term=-1 best=0 id o t
  for id in 1 2 3 4 5; do
    o=$(name_for_id "$id")
    t=$(docker logs --tail 120 "$o" 2>&1 | grep -ao "became leader at term [0-9]*" | tail -1 | grep -ao "[0-9]*$")
    if [ -n "$t" ] && [ "$t" -gt "$best_term" ]; then best_term=$t; best=$id; fi
  done
  echo "$best"
}

refresher(){
  while [ -f "$RUN_FLAG" ]; do
    local bl s; bl=$(cat "$BL_FILE"); s=$(( $(cat "$SEQ_FILE") + 1 )); echo "$s" > "$SEQ_FILE"
    for o in "${ORDERERS[@]}"; do
      docker exec "$o" sh -c "printf '%s' '{\"blacklist\":$bl,\"seq\":$s,\"fail_open\":false}' > /tmp/bora-advice.json" 2>/dev/null &
    done
    wait; sleep 0.25
  done
}
set_blacklist(){ echo "$1" > "$BL_FILE"; sleep 1.5; }

# returns "wins liveness_ok distinct" for N forced elections
run_phase(){ # $1=label
  local wins=0 live=0 distinct=0 prev="" i L LC NL
  for i in $(seq 1 "$N_ELECT"); do
    L=$(leader_id); LC=$(name_for_id "$L"); [ -z "$LC" ] && LC=orderer.example.com
    docker restart "$LC" >/dev/null 2>&1; sleep 13
    NL=$(leader_id)
    [ "$NL" = "3" ] && wins=$((wins+1))
    [ -n "$NL" ] && [ "$NL" != "0" ] && live=$((live+1))
    [ -n "$NL" ] && [ "$NL" != "$prev" ] && distinct=$((distinct+1)); prev="$NL"
    echo "    [$1] election $i: restart id=$L -> leader id=$NL" | tee -a "$OUT/summary.txt"
  done
  echo "$wins $live $distinct"
}

echo "label,seed,orderer3_wins,n_elect,liveness_ok,distinct_leaders" > "$OUT/results.csv"
echo "=== sidecar socket? ===" | tee "$OUT/summary.txt"
docker exec orderer.example.com sh -c 'test -S /var/run/raft-advisor.sock && echo SOCKET_OK || echo SOCKET_MISSING' | tee -a "$OUT/summary.txt"

set_blacklist "[]"; refresher & REF=$!
echo "[refresher] pid=$REF" | tee -a "$OUT/summary.txt"

for s in $(seq 1 "$SEEDS"); do
  echo "######## SEED $s ########" | tee -a "$OUT/summary.txt"
  echo "  --- A: no BORA (blacklist=[]) ---" | tee -a "$OUT/summary.txt"
  set_blacklist "[]"
  read wa la da < <(run_phase "A_s$s")
  echo "  [A_s$s] orderer3 won $wa/$N_ELECT | liveness $la/$N_ELECT | $da distinct" | tee -a "$OUT/summary.txt"
  echo "A_noBORA,$s,$wa,$N_ELECT,$la,$da" >> "$OUT/results.csv"

  echo "  --- B: BORA sustained (blacklist=[3]) ---" | tee -a "$OUT/summary.txt"
  set_blacklist "[3]"
  read wb lb db < <(run_phase "B_s$s")
  echo "  [B_s$s] orderer3 won $wb/$N_ELECT | liveness $lb/$N_ELECT | $db distinct" | tee -a "$OUT/summary.txt"
  echo "B_BORA,$s,$wb,$N_ELECT,$lb,$db" >> "$OUT/results.csv"
done

set_blacklist "[]"; rm -f "$RUN_FLAG"; sleep 1; kill "$REF" 2>/dev/null || true
echo "LEADER_ACQ_LS3_DONE (results: $OUT)" | tee -a "$OUT/summary.txt"
echo "=== results.csv ===" | tee -a "$OUT/summary.txt"
cat "$OUT/results.csv" | tee -a "$OUT/summary.txt"
