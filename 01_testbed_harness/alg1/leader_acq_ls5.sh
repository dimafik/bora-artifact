#!/usr/bin/env bash
# LS5 = LS4 + robustness guard. The only change vs LS4: in phase B we
# RE-ASSERT and VERIFY orderer3's blacklist=[3] advice directly (with retry)
# immediately before AND after each forced restart, closing the transient
# advice-delivery gap that let orderer3 slip through once under docker-daemon
# stress in LS4 (the OCI "broken pipe" / "stopped container" hiccups).
# v3 sidecar (per-read monotonic seq) must already be deployed.
set -u
N_ELECT="${N_ELECT:-10}"
SEEDS="${SEEDS:-3}"
SIDECAR=/tmp/bora-sidecar
OUT=/mnt/d/fabric-d2/results/leaderacq5_$(date +%Y%m%d-%H%M%S); mkdir -p "$OUT"
BL_FILE="$OUT/blacklist.json"; echo "[]" > "$BL_FILE"
RUN_FLAG="$OUT/refresh.on"; touch "$RUN_FLAG"
ELOG="$OUT/elections.log"; : > "$ELOG"
RES="$OUT/results.csv"; echo "label,seed,orderer3_wins,n_elect,liveness_ok,distinct_leaders" > "$RES"
SUM="$OUT/summary.txt"; : > "$SUM"
ALL=(orderer.example.com orderer2.example.com orderer3.example.com orderer4.example.com orderer5.example.com)
name_for_id(){ case $1 in 1) echo orderer.example.com;; 2) echo orderer2.example.com;; 3) echo orderer3.example.com;; 4) echo orderer4.example.com;; 5) echo orderer5.example.com;; *) echo "";; esac; }
log(){ echo "$*" | tee -a "$SUM"; }

ensure_sidecar(){
  docker exec "$1" sh -c 'test -S /var/run/raft-advisor.sock' 2>/dev/null && return 0
  docker exec "$1" sh -c "pkill -f bora-sidecar 2>/dev/null; rm -f /var/run/raft-advisor.sock" 2>/dev/null
  docker exec -d "$1" sh -c "setsid $SIDECAR >/tmp/bora-sidecar.log 2>&1 </dev/null" 2>/dev/null
  sleep 1
}

# write a blacklist to orderer3's advice file and VERIFY it stuck (retry)
assert_bl_o3(){ # $1 = json blacklist e.g. [3] or []
  local want="$1" got try
  for try in 1 2 3 4 5 6; do
    ensure_sidecar orderer3.example.com
    docker exec orderer3.example.com sh -c "printf '%s' '{\"blacklist\":$want,\"seq\":1,\"fail_open\":false}' > /tmp/bora-advice.json" 2>/dev/null
    got=$(docker exec orderer3.example.com sh -c 'cat /tmp/bora-advice.json' 2>/dev/null)
    echo "$got" | grep -qF "\"blacklist\":$want" && return 0
    sleep 0.5
  done
  return 1
}

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

# background refresher only self-heals orderer3 sidecar + keeps advice fresh
refresher(){
  while [ -f "$RUN_FLAG" ]; do
    ensure_sidecar orderer3.example.com
    local bl; bl=$(cat "$BL_FILE")
    docker exec orderer3.example.com sh -c "printf '%s' '{\"blacklist\":$bl,\"seq\":1,\"fail_open\":false}' > /tmp/bora-advice.json" 2>/dev/null
    sleep 0.4
  done
}

run_phase(){ # $1=label  $2=blacklist([] or [3])  -> sets WINS LIVE DIST
  WINS=0; LIVE=0; DIST=0; local prev="" i L LC NL bl="$2"
  for i in $(seq 1 "$N_ELECT"); do
    [ "$bl" = "[3]" ] && assert_bl_o3 "[3]"
    L=$(leader_id); LC=$(name_for_id "$L"); [ -z "$LC" ] && LC=orderer2.example.com
    docker restart "$LC" >/dev/null 2>&1; sleep 6
    [ "$bl" = "[3]" ] && assert_bl_o3 "[3]"     # re-assert during the election window
    sleep 7
    NL=$(leader_id)
    [ "$NL" = "3" ] && WINS=$((WINS+1))
    [ "$NL" != "0" ] && LIVE=$((LIVE+1))
    [ "$NL" != "0" ] && [ "$NL" != "$prev" ] && DIST=$((DIST+1)); prev="$NL"
    echo "[$1] e$i: restart id=$L -> leader id=$NL" >> "$ELOG"
  done
}

log "=== LS5 start: N_ELECT=$N_ELECT SEEDS=$SEEDS ==="
for o in "${ALL[@]}"; do ensure_sidecar "$o"; done
echo "[]" > "$BL_FILE"; refresher & REF=$!
log "[refresher] pid=$REF"

for s in $(seq 1 "$SEEDS"); do
  log "######## SEED $s ########"
  echo "[]" > "$BL_FILE"; assert_bl_o3 "[]"; sleep 1
  run_phase "A_s$s" "[]"
  log "  [A_s$s no-BORA] orderer3 won $WINS/$N_ELECT | liveness $LIVE/$N_ELECT | $DIST distinct"
  echo "A_noBORA,$s,$WINS,$N_ELECT,$LIVE,$DIST" >> "$RES"

  echo "[3]" > "$BL_FILE"; assert_bl_o3 "[3]"; sleep 1
  run_phase "B_s$s" "[3]"
  log "  [B_s$s BORA]    orderer3 won $WINS/$N_ELECT | liveness $LIVE/$N_ELECT | $DIST distinct"
  echo "B_BORA,$s,$WINS,$N_ELECT,$LIVE,$DIST" >> "$RES"
done

echo "[]" > "$BL_FILE"; rm -f "$RUN_FLAG"; sleep 1; kill "$REF" 2>/dev/null || true
log "LEADER_ACQ_LS5_DONE (results: $OUT)"
cat "$RES" | tee -a "$SUM"
