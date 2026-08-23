#!/usr/bin/env bash
# ============================================================================
# LS4: Adversarial leadership-acquisition under SUSTAINED BORA advice.
# Rewrite of LS3 fixing: (a) stdout-capture SIGPIPE bug (functions teed to a
# captured pipe -> died after 1 iteration); (b) docker-daemon overload from a
# 5x/0.25s refresher -> now orderer3-only, 0.4s; (c) leader-detect id=0 ->
# tail 400 + retry; (d) docker restart kills the in-container sidecar -> the
# refresher self-heals orderer3's sidecar (the only one that must stay up,
# since orderer3 is the blacklisted target).
#
# Target = orderer3 (healthy, NO network delay; a delayed node cannot win
# elections at all, so BORA's leadership value is only demonstrable against a
# healthy adversary). N forced elections per seed by restarting the current
# leader; count how often orderer3 acquires leadership.
#   A (blacklist=[]):  orderer3 wins ~1/(N-1).
#   B (blacklist=[3], sustained): orderer3 wins ~0.
# ============================================================================
set -u
N_ELECT="${N_ELECT:-10}"
SEEDS="${SEEDS:-3}"
SIDECAR=/tmp/bora-sidecar
OUT=/mnt/d/fabric-d2/results/leaderacq4_$(date +%Y%m%d-%H%M%S); mkdir -p "$OUT"
BL_FILE="$OUT/blacklist.json"; echo "[]" > "$BL_FILE"
SEQ_FILE="$OUT/seq.txt"; echo 4000 > "$SEQ_FILE"
RUN_FLAG="$OUT/refresh.on"; touch "$RUN_FLAG"
ELOG="$OUT/elections.log"; : > "$ELOG"
RES="$OUT/results.csv"; echo "label,seed,orderer3_wins,n_elect,liveness_ok,distinct_leaders" > "$RES"
SUM="$OUT/summary.txt"; : > "$SUM"
ALL=(orderer.example.com orderer2.example.com orderer3.example.com orderer4.example.com orderer5.example.com)
name_for_id(){ case $1 in 1) echo orderer.example.com;; 2) echo orderer2.example.com;; 3) echo orderer3.example.com;; 4) echo orderer4.example.com;; 5) echo orderer5.example.com;; *) echo "";; esac; }

log(){ echo "$*" | tee -a "$SUM"; }

ensure_sidecar(){ # $1=orderer host  (start if socket missing)
  docker exec "$1" sh -c 'test -S /var/run/raft-advisor.sock' 2>/dev/null && return 0
  docker exec "$1" sh -c "pkill -f bora-sidecar 2>/dev/null; rm -f /var/run/raft-advisor.sock" 2>/dev/null
  docker exec -d "$1" sh -c "setsid $SIDECAR >/tmp/bora-sidecar.log 2>&1 </dev/null" 2>/dev/null
  sleep 1
}

# robust leader detection: node with highest "became leader at term T"; retry
leader_id(){
  local try best_term best id o t
  for try in 1 2 3 4 5; do
    best_term=-1; best=0
    for id in 1 2 3 4 5; do
      o=$(name_for_id "$id")
      t=$(docker logs --tail 400 "$o" 2>&1 | grep -ao "became leader at term [0-9]*" | tail -1 | grep -ao "[0-9]*$")
      if [ -n "$t" ] && [ "$t" -gt "$best_term" ]; then best_term=$t; best=$id; fi
    done
    [ "$best" != "0" ] && { echo "$best"; return; }
    sleep 2
  done
  echo "0"
}

# background: keep orderer3's advice fresh (seq bump faster than 500ms tick)
# and self-heal orderer3's sidecar so suppression never silently lapses.
refresher(){
  while [ -f "$RUN_FLAG" ]; do
    ensure_sidecar orderer3.example.com
    local bl s; bl=$(cat "$BL_FILE"); s=$(( $(cat "$SEQ_FILE") + 1 )); echo "$s" > "$SEQ_FILE"
    docker exec orderer3.example.com sh -c "printf '%s' '{\"blacklist\":$bl,\"seq\":$s,\"fail_open\":false}' > /tmp/bora-advice.json" 2>/dev/null
    sleep 0.4
  done
}
set_blacklist(){ echo "$1" > "$BL_FILE"; sleep 2; }   # let refresher propagate

log "=== LS4 start: N_ELECT=$N_ELECT SEEDS=$SEEDS ==="
for o in "${ALL[@]}"; do ensure_sidecar "$o"; done
log "sidecars ensured"

set_blacklist "[]"; refresher & REF=$!
log "[refresher] orderer3-only pid=$REF"

run_phase(){ # $1=label e.g. A_s1 ; sets globals WINS LIVE DIST
  WINS=0; LIVE=0; DIST=0; local prev="" i L LC NL
  for i in $(seq 1 "$N_ELECT"); do
    L=$(leader_id); LC=$(name_for_id "$L"); [ -z "$LC" ] && LC=orderer2.example.com
    docker restart "$LC" >/dev/null 2>&1; sleep 12
    NL=$(leader_id)
    [ "$NL" = "3" ] && WINS=$((WINS+1))
    [ "$NL" != "0" ] && LIVE=$((LIVE+1))
    [ "$NL" != "0" ] && [ "$NL" != "$prev" ] && DIST=$((DIST+1)); prev="$NL"
    echo "[$1] e$i: restart id=$L -> leader id=$NL" >> "$ELOG"
  done
}

for s in $(seq 1 "$SEEDS"); do
  log "######## SEED $s ########"
  set_blacklist "[]"
  run_phase "A_s$s"
  log "  [A_s$s no-BORA] orderer3 won $WINS/$N_ELECT | liveness $LIVE/$N_ELECT | $DIST distinct"
  echo "A_noBORA,$s,$WINS,$N_ELECT,$LIVE,$DIST" >> "$RES"

  ensure_sidecar orderer3.example.com
  set_blacklist "[3]"
  run_phase "B_s$s"
  log "  [B_s$s BORA]    orderer3 won $WINS/$N_ELECT | liveness $LIVE/$N_ELECT | $DIST distinct"
  echo "B_BORA,$s,$WINS,$N_ELECT,$LIVE,$DIST" >> "$RES"
done

set_blacklist "[]"; rm -f "$RUN_FLAG"; sleep 1; kill "$REF" 2>/dev/null || true
log "LEADER_ACQ_LS4_DONE (results: $OUT)"
log "=== results.csv ==="
cat "$RES" | tee -a "$SUM"
