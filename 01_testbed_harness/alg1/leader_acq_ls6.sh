#!/usr/bin/env bash
# ============================================================================
# LS6: clean adversarial leadership-acquisition. Root-cause fix over LS4/LS5:
# the 0.4s advice-REWRITE loop raced with docker-daemon stress (printf > file
# is non-atomic) and momentarily blanked orderer3's advice -> suppression
# gaps -> orderer3 slipped through (B_s1=1, B_s2=2 in LS4). Fix: write the
# blacklist to orderer3's advice file ONCE per phase (verified, read-first /
# write-only-if-wrong), and never rewrite it during the phase. The v3 sidecar
# (per-read monotonic seq) keeps serving that file fresh every tick, so a
# standing [3] is enforced continuously with ZERO writes during elections.
# The background loop now ONLY self-heals orderer3's sidecar process (which
# dies if orderer3 is ever restarted); /tmp/bora-advice.json survives restart.
#
# Target = orderer3 (healthy, no delay). N forced elections/seed by restarting
# the current leader. A: blacklist=[] -> orderer3 wins ~1/(N-1).
#                       B: blacklist=[3] -> orderer3 wins 0 (liveness kept).
# ============================================================================
set -u
N_ELECT="${N_ELECT:-10}"
SEEDS="${SEEDS:-3}"
SIDECAR=/tmp/bora-sidecar
OUT=/mnt/d/fabric-d2/results/leaderacq6_$(date +%Y%m%d-%H%M%S); mkdir -p "$OUT"
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

# write blacklist to orderer3 ONCE; read-first, write only if wrong; verify.
set_o3_bl(){ # $1 = [] or [3]
  local want="$1" got try
  for try in 1 2 3 4 5 6 7 8; do
    ensure_sidecar orderer3.example.com
    got=$(docker exec orderer3.example.com sh -c 'cat /tmp/bora-advice.json' 2>/dev/null)
    echo "$got" | grep -qF "\"blacklist\":$want" && return 0
    docker exec orderer3.example.com sh -c "printf '%s' '{\"blacklist\":$want,\"seq\":1,\"fail_open\":false}' > /tmp/bora-advice.json" 2>/dev/null
    sleep 0.5
  done
  log "  WARN: could not set orderer3 blacklist=$want"; return 1
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

# background: ONLY self-heal orderer3's sidecar (no advice writes here).
healer(){ while [ -f "$RUN_FLAG" ]; do ensure_sidecar orderer3.example.com; sleep 0.5; done; }

run_phase(){ # $1=label  -> sets WINS LIVE DIST  (advice already set by caller)
  WINS=0; LIVE=0; DIST=0; local prev="" i L LC NL
  for i in $(seq 1 "$N_ELECT"); do
    L=$(leader_id); LC=$(name_for_id "$L"); [ -z "$LC" ] && LC=orderer2.example.com
    docker restart "$LC" >/dev/null 2>&1; sleep 13
    NL=$(leader_id)
    [ "$NL" = "3" ] && WINS=$((WINS+1))
    [ "$NL" != "0" ] && LIVE=$((LIVE+1))
    [ "$NL" != "0" ] && [ "$NL" != "$prev" ] && DIST=$((DIST+1)); prev="$NL"
    echo "[$1] e$i: restart id=$L -> leader id=$NL" >> "$ELOG"
  done
}

log "=== LS6 start: N_ELECT=$N_ELECT SEEDS=$SEEDS ==="
for o in "${ALL[@]}"; do ensure_sidecar "$o"; done
healer & HEAL=$!
log "[healer] orderer3 sidecar pid=$HEAL"

for s in $(seq 1 "$SEEDS"); do
  log "######## SEED $s ########"
  set_o3_bl "[]"; sleep 1
  run_phase "A_s$s"
  log "  [A_s$s no-BORA] orderer3 won $WINS/$N_ELECT | liveness $LIVE/$N_ELECT | $DIST distinct"
  echo "A_noBORA,$s,$WINS,$N_ELECT,$LIVE,$DIST" >> "$RES"

  set_o3_bl "[3]"; sleep 1
  run_phase "B_s$s"
  log "  [B_s$s BORA]    orderer3 won $WINS/$N_ELECT | liveness $LIVE/$N_ELECT | $DIST distinct"
  echo "B_BORA,$s,$WINS,$N_ELECT,$LIVE,$DIST" >> "$RES"
done

set_o3_bl "[]"; rm -f "$RUN_FLAG"; sleep 1; kill "$HEAL" 2>/dev/null || true
log "LEADER_ACQ_LS6_DONE (results: $OUT)"
cat "$RES" | tee -a "$SUM"
