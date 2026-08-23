#!/usr/bin/env bash
# R1-3: what does a WRONG prediction cost, as a function of where the learner's
# output enters the protocol?
#
#   Arm A  vanilla    advice ignored; no learner in the loop
#   Arm C  BORA       advice removes CANDIDACY only (tick guard + vote guard)
#   Arm D  authority  advice DEMOTES: if the flagged node is the incumbent it is
#                     forced out immediately.  This is the AWARE / BFTBrain
#                     contract -- the learner can move the leader -- implemented
#                     on our substrate.  It is NOT those systems, and no number
#                     here is a measurement of them; the point is that A, C and D
#                     differ ONLY in that entry point.
#
# The independent variable is the false-positive rate p.  Every arm replays the
# SAME pre-generated false-positive schedule for a given (p, seed), so the arms
# are paired and the difference between them cannot be RNG.
#
# Deliberately NOT reusing x1_closedloop.sh: that script produced numbers already
# reported, and mutating it would put those numbers out of reach of re-running.
#
#   r13_authority.sh <N> <seeds> <dur_s> [rates...]
#   r13_authority.sh 7 1 120 0 20          # pilot
#   r13_authority.sh 7 3 300 0 5 10 20     # full
set -u
N="${1:?need N}"; SEEDS="${2:-1}"; DUR="${3:-300}"
if [ $# -gt 3 ]; then shift 3; RATES=("$@"); else RATES=(0 20); fi
F=$(( (N - 1) / 2 ))
TARGET=3
D=/mnt/d/fabric-d2
TN="$D/fabric-samples/test-network"
BT="$D/results/bt.json"
BTFP="$D/results/bt_r13.json"
# The Windows PowerShell path stays on PATH on purpose: the predictor daemon is a
# Windows-side process (torch + the model live there), started through
# restart_daemon.ps1.  The inherited harness PATH line drops the interop
# directories, and then start_daemon.sh fails with "powershell.exe: command not
# found" -- which the daemon gate catches, but only after a wasted bring-up.
export PATH=/tmp/bin:"$D"/fabric-samples/bin-linux/bin:/usr/local/bin:/usr/bin:/bin:/mnt/c/WINDOWS/System32/WindowsPowerShell/v1.0

OUT="$D/results/r13_N${N}_$(date +%m%d-%H%M%S)"; mkdir -p "$OUT"
echo "arm,rate,seed,dur,leader_changes,target_led_s,fp_events,fp_on_leader,demotions,demote_TP,demote_FP,safety_viol,final_leader" \
  > "$OUT/cells.csv"

host(){ [ "$1" = 1 ] && echo orderer || echo "orderer$1"; }
cont(){ echo "$(host $1).example.com"; }
ORD=(); for i in $(seq 1 "$N"); do ORD+=("$(cont $i)"); done

log(){ echo "[$(date +%H:%M:%S)] $*" | tee -a "$OUT/run.log"; }

# ---------------------------------------------------------------- leader state
# Docker log timestamps give both the count of leader changes and the gaps
# between "lost leadership" and the next "leader changed", which is the
# unavailability a wrong prediction actually buys.
# Reading the leader out of `docker logs` needs the last "Raft leader changed"
# line to still be inside the tail window.  On a quiet cluster that line can be
# hours old: the first working pilot returned leader=0 for every cell, so the
# authority arm's `if leader in blacklist` never fired and every metric came out
# zero -- a completely silent no-op experiment.  The ops endpoint states the
# current leader directly and costs one local HTTP call per orderer.
gport(){ case $1 in 1) echo 7050;; 2) echo 8050;; *) echo $(( 10050 + 1000 * ($1 - 3) ));; esac; }
opsport(){ echo $(( $(gport "$1") + 5 )); }
leader_now(){
  local id v
  for id in $(seq 1 "$N"); do
    v=$(curl -s --max-time 2 "localhost:$(opsport "$id")/metrics" 2>/dev/null \
        | grep -E '^consensus_etcdraft_is_leader' | grep -oE '[01]$' | head -1)
    [ "$v" = "1" ] && { echo "$id"; return; }
  done
  echo 0
}

collect_changes(){  # <since_iso> -> lines "ts old new"
  local since="$1" id o
  for id in $(seq 1 "$N"); do o=$(cont $id)
    docker logs --timestamps --since "$since" "$o" 2>&1 \
      | grep -aE 'Raft leader changed: [0-9]+ -> [0-9]+' \
      | sed -E 's/^([^ ]+) .*Raft leader changed: ([0-9]+) -> ([0-9]+).*/\1 \2 \3/'
  done | sort -u
}

# ---------------------------------------------------------------- advice paths
set_all(){ for o in "${ORD[@]}"; do
  docker exec "$o" sh -c "printf '%s' '{\"blacklist\":$1,\"seq\":1,\"fail_open\":false}' > /tmp/bora-advice.json" 2>/dev/null
done; }

# NOTE ON THE PID DANCE.  These helpers must NOT be called as `PID=$(helper)`.
# Command substitution waits for stdout to close, and a background loop started
# inside it holds that pipe open for as long as it runs, so `$( (loop) & echo $!)`
# blocks forever instead of returning a PID.  That is what hung the first pilot
# for seven hours in cell one with no error and every container healthy.
# The helpers therefore assign to the caller's variable directly (bash is
# dynamically scoped, so `local PUSHPID` in cell() receives it) and redirect the
# background job's output so it never shares this shell's stdout.
push_empty(){
  ( while [ -f /tmp/r13.on ]; do set_all "[]"; sleep 0.5; done ) >/dev/null 2>&1 &
  PUSHPID=$!
}
push_from(){   # keep pushing the given advice file to every orderer
  local src="$1"
  ( while [ -f /tmp/r13.on ]; do
      bl=$(grep -oE '"blacklist" *: *\[[0-9, ]*\]' "$src" 2>/dev/null | grep -oE '\[[0-9, ]*\]' | tr -d ' ')
      [ -n "$bl" ] && set_all "$bl"
      sleep 0.3
    done ) >/dev/null 2>&1 &
  PUSHPID=$!
}

# ---------------------------------------------------------------- authority arm
# The actuator for "the learner moved the leader".  Pausing the incumbent past
# the election timeout is exactly the demotion AWARE/BFTBrain's interface
# permits; the cluster then elects someone else.
authority_loop(){
  local logf="$1"
  # leader_now() costs one `docker logs` per orderer, so polling it twice a
  # second at N=7 is 14 docker calls/s -- enough load to perturb the very
  # timings this experiment measures.  Poll the cheap thing (the advice file)
  # often and the expensive thing (the leader) only when the advice is non-empty.
  ( local hits=0
    while [ -f /tmp/r13.on ]; do
      bl=$(grep -oE '"blacklist" *: *\[[0-9, ]*\]' "$BTFP" 2>/dev/null | grep -oE '[0-9]+' | tr '\n' ' ')
      if [ -z "$bl" ]; then sleep 0.5; continue; fi
      L=$(leader_now)
      if [ -n "$L" ] && [ "$L" != 0 ] && printf ' %s ' "$bl" | grep -q " $L "; then
        hits=$((hits+1))
        # Which kind of detection moved the leader matters more than the count.
        # A TRUE positive on the incumbent is the case where authority helps and
        # BORA deliberately does nothing (ALR); a FALSE positive on the incumbent
        # is the case where authority costs a leader change and BORA costs zero.
        # Reporting only the total would hide half of the trade-off.
        tset=$(grep -oE '"true" *: *\[[0-9, ]*\]' "$BTFP" 2>/dev/null | grep -oE '[0-9]+' | tr '\n' ' ')
        cause=FP; printf ' %s ' "$tset" | grep -q " $L " && cause=TP
        echo "$(date +%s.%N) demote leader=$L cause=$cause bl=[$bl] true=[$tset]" >> "$logf"
        docker pause "$(cont "$L")" >/dev/null 2>&1
        sleep 9
        docker unpause "$(cont "$L")" >/dev/null 2>&1
        sleep 4
      fi
      sleep 0.5
    done
    echo "demotions=$hits" >> "$logf" ) >/dev/null 2>&1 &
  AUTHPID=$!
}

# ---------------------------------------------------------------- one cell
cell(){
  local arm="$1" rate="$2" seed="$3"
  local tag="${arm}_p${rate}_s${seed}"
  local cdir="$OUT/$tag"; mkdir -p "$cdir"
  log "cell $tag (dur=${DUR}s)"

  set_all "[]"
  rm -f "$BTFP"; touch /tmp/r13.on
  # RFC3339 with the Z: without it docker reads the value as LOCAL time, which
  # on a KST box shifts the collection window by nine hours and silently returns
  # either everything or nothing.
  local since; since=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  # The window's leader timeline starts here.  Without it a cell in which nobody
  # changed leader has an EMPTY timeline, and "was the false positive aimed at
  # the incumbent?" silently answers no for every event.
  leader_now > "$cdir/leader0.txt"

  # stderr goes to a FILE, not /dev/null.  The injector died on its first loop
  # iteration for two whole pilots (a TypeError one line into the merge) and the
  # only symptom was that nothing ever happened -- because the traceback had been
  # discarded.  A silent component is worse than a failing one.
  python3 "$D/alg1/r13_fp_inject.py" --rate "$rate" --seed "$seed" --dur "$DUR" \
      --n "$N" --target "$TARGET" --src "$BT" --out "$BTFP" \
      --log "$cdir/fp.log" >/dev/null 2>"$cdir/fp.err" &
  local FPPID=$!
  python3 "$D/alg1/r13_fp_inject.py" --rate "$rate" --seed "$seed" --dur "$DUR" \
      --n "$N" --target "$TARGET" --dump-schedule > "$cdir/schedule.csv" 2>/dev/null
  sleep 3
  # Gate the injector the same way the daemon and the attack are gated: prove it
  # is publishing before spending the cell's runtime on it.
  if [ ! -s "$BTFP" ]; then
    log "GATE FAIL: injector wrote no advice to $BTFP"
    [ -s "$cdir/fp.err" ] && tail -3 "$cdir/fp.err" | tee -a "$OUT/run.log"
    rm -f /tmp/r13.on; kill "$FPPID" 2>/dev/null; exit 1
  fi

  local PUSHPID="" AUTHPID=""
  case "$arm" in
    A) push_empty ;;
    C) push_from "$BTFP" ;;
    D) push_empty; authority_loop "$cdir/authority.log" ;;
  esac
  log "  arm=$arm push=$PUSHPID auth=${AUTHPID:-none} (running ${DUR}s)"

  sleep "$DUR"
  rm -f /tmp/r13.on
  sleep 2
  kill "$FPPID" "$PUSHPID" $AUTHPID 2>/dev/null || true
  set_all "[]"

  collect_changes "$since" > "$cdir/leader_changes.txt"
  # Metrics are derived in python from the raw timeline + schedule so that every
  # arm is measured the same way (see r13_metrics.py for the two counting traps).
  local M; M=$(python3 "$D/alg1/r13_metrics.py" "$cdir" "$N" "$TARGET" "$DUR")
  local LC FPE FPL TLS
  IFS=, read -r LC FPE FPL TLS <<< "$M"
  local DEM=0 DTP=0 DFP=0
  if [ -f "$cdir/authority.log" ]; then
    DEM=$(grep -c ' demote ' "$cdir/authority.log" || true)
    DTP=$(grep -c 'cause=TP' "$cdir/authority.log" || true)
    DFP=$(grep -c 'cause=FP' "$cdir/authority.log" || true)
  fi
  local FL; FL=$(leader_now)
  # any orderer PANIC or fatal is a safety-relevant abort; expected 0 everywhere
  local SV=0
  for o in "${ORD[@]}"; do
    SV=$((SV + $(docker logs --since "$since" "$o" 2>&1 | grep -acE 'PANI|FATAL' || true)))
  done
  echo "$arm,$rate,$seed,$DUR,$LC,$TLS,$FPE,$FPL,$DEM,$DTP,$DFP,$SV,$FL" >> "$OUT/cells.csv"
  log "  -> leader_changes=$LC target_led=${TLS}s fp=$FPE fp_on_leader=$FPL demote=$DEM (TP=$DTP FP=$DFP) safety=$SV leader=$FL"
}

# ---------------------------------------------------------------- shared setup
# The degraded node and the live detector are common to every arm: the arms
# differ only in where the detector's output goes.  Both are started once, and
# both are GATED -- a dead pumba turns the run into a no-attack run and a dead
# daemon turns the true positives into stale ones, and neither raises an error
# on its own.  (An earlier sweep in this project lost a whole arm that way.)
FEED="$D/results/rtt_feed.csv"
start_probe(){
  docker rm -f rtt-probe >/dev/null 2>&1; rm -f "$FEED"
  docker run -d --name rtt-probe --network fabric_test -v /mnt/d/fabric-d2:/feed \
    -v "$D/alg1/rtt_probe_n.py:/rtt_probe.py" -e FEED=/feed/results/rtt_feed.csv -e N="$N" \
    python:3.11-slim python /rtt_probe.py >/dev/null 2>&1
}
# pumba reverts the netem qdisc on SIGTERM and NOT on SIGKILL.  `docker rm -f`
# sends SIGKILL, so it leaves +200 ms welded to the target: the next run's
# `tc qdisc add ... root` then fails with "file exists", and had the run not been
# gated it would have proceeded with a permanently degraded node and no attack
# container.  Always stop first, and verify the qdisc afterwards.
stop_attack(){
  docker stop -t 15 pumba-r13 >/dev/null 2>&1
  docker rm -f pumba-r13 >/dev/null 2>&1
}
qdisc_of(){  # <container> -> qdisc line for eth0
  docker run --rm --net="container:$1" --cap-add=NET_ADMIN gaiadocker/iproute2 \
    qdisc show dev eth0 2>/dev/null | head -1
}
start_attack(){
  stop_attack; sleep 3
  local q; q=$(qdisc_of "$(cont $TARGET)")
  case "$q" in
    *netem*) log "GATE FAIL: residual netem on $(cont $TARGET) [$q]; restart that container first"; exit 1;;
  esac
  docker run -d --name pumba-r13 -v /var/run/docker.sock:/var/run/docker.sock gaiaadm/pumba:latest \
    --log-level warning netem --tc-image gaiadocker/iproute2 --duration 600m \
    delay --time 200 "$(cont $TARGET)" >/dev/null 2>&1
  sleep 8
  if docker logs pumba-r13 2>&1 | grep -q 'level=fatal'; then
    log "GATE FAIL: pumba could not apply netem:"; docker logs pumba-r13 2>&1 | tail -2 | tee -a "$OUT/run.log"; exit 1
  fi
  q=$(qdisc_of "$(cont $TARGET)")
  case "$q" in
    *netem*) log "  attack OK: $(cont $TARGET) [$q]";;
    *) log "GATE FAIL: pumba is up but no netem on the target [$q]"; exit 1;;
  esac
}
check_attack(){
  docker ps --format '{{.Names}}' | grep -q '^pumba-r13$' \
    || { log "GATE FAIL: pumba-r13 is gone - the degraded node is no longer degraded"; exit 1; }
}
gate_daemon(){
  [ -f "$BT" ] || { log "GATE FAIL: $BT missing - predictor daemon not running"; exit 1; }
  local age; age=$(( $(date +%s) - $(stat -c %Y "$BT") ))
  [ "$age" -le 15 ] || { log "GATE FAIL: bt.json is ${age}s stale - the daemon is not publishing"; exit 1; }
  local c want r
  r=$(grep -oE '"r" *: *[0-9]+' "$BT" | grep -oE '[0-9]+$')
  c=$(grep -oE '"cap" *: *[0-9]+' "$BT" | grep -oE '[0-9]+$')
  want=$(( F - ${r:-0} - 1 )); [ "$want" -lt 0 ] && want=0
  [ "${c:-x}" = "$want" ] || { log "GATE FAIL: bt.json cap=$c but N=$N f=$F r=$r implies $want (daemon belongs to another N)"; exit 1; }
  log "  daemon gate OK: bt.json ${age}s old, r=$r cap=$c"
}

# ---------------------------------------------------------------- run
log "R1-3 interface experiment  N=$N f=$F seeds=$SEEDS dur=$DUR rates=${RATES[*]}"
log "OUT=$OUT"
start_probe; start_attack; sleep 20
bash "$D/alg1/start_daemon.sh" "$N" "$F" | tee -a "$OUT/run.log"
sleep 25
gate_daemon; check_attack
for rate in "${RATES[@]}"; do
  for seed in $(seq 1 "$SEEDS"); do
    for arm in A C D; do check_attack; gate_daemon; cell "$arm" "$rate" "$seed"; done
  done
done
stop_attack; docker rm -f rtt-probe >/dev/null 2>&1
log "netem after teardown: $(qdisc_of "$(cont $TARGET)")"
log "done -> $OUT/cells.csv"
column -s, -t < "$OUT/cells.csv" | tee -a "$OUT/run.log"
