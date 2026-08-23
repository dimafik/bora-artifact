#!/usr/bin/env bash
# R1-3, second design.  What does a WRONG prediction cost, per interface?
#
# WHY v1 WAS NOT ENOUGH.  v1 ran the cluster undisturbed and asked whether the
# leader moved.  It never did in the advisory arms -- which is the intended
# behaviour, but it is ALSO exactly what a dead advice path looks like.  With a
# stable leader there are no elections, and BORA's guard only acts at election
# time, so arm C had no opportunity to demonstrate that it was alive.  "BORA
# absorbed 60 false positives" and "the advice never reached the guard" produced
# identical tables.
#
# THE FIX.  Force elections in EVERY arm, and hold each false positive long
# enough to still be in force when the election happens.  Then:
#
#   Arm A  vanilla     the falsely-flagged healthy node wins at its chance share
#   Arm C  BORA        it must win ZERO -- a positive control for the guard, and
#                      the leader still changes, so liveness is visible too
#   Arm D  authority   the leader additionally moves whenever the learner names
#                      the incumbent, election or no election
#
# The advice actually delivered to an orderer is sampled at every election and
# written to the trace, so "the guard saw it" is recorded rather than assumed.
#
#   r13_v2.sh <N> <seeds> <dur_s> [rates...]
set -u
N="${1:?need N}"; SEEDS="${2:-1}"; DUR="${3:-300}"
if [ $# -gt 3 ]; then shift 3; RATES=("$@"); else RATES=(0 20); fi
F=$(( (N - 1) / 2 ))
CAP=$(( F - 1 ))            # Algorithm 1: |B_t| <= f - r - 1, r = 0 here
TARGET=3
ELEC_EVERY=30               # seconds between forced elections
D=/mnt/d/fabric-d2
BT="$D/results/bt.json"
BTFP="$D/results/bt_r13.json"
export PATH=/tmp/bin:"$D"/fabric-samples/bin-linux/bin:/usr/local/bin:/usr/bin:/bin:/mnt/c/WINDOWS/System32/WindowsPowerShell/v1.0

OUT="$D/results/r13v2_N${N}_$(date +%m%d-%H%M%S)"; mkdir -p "$OUT"
echo "arm,rate,seed,dur,elections,elec_with_fp,fp_node_wins,leader_changes,demotions,demote_TP,demote_FP,liveness_fail,mean_ttl_s,advice_seen,safety_viol" \
  > "$OUT/cells.csv"

host(){ [ "$1" = 1 ] && echo orderer || echo "orderer$1"; }
cont(){ echo "$(host $1).example.com"; }
gport(){ case $1 in 1) echo 7050;; 2) echo 8050;; *) echo $(( 10050 + 1000 * ($1 - 3) ));; esac; }
opsport(){ echo $(( $(gport "$1") + 5 )); }
ORD=(); for i in $(seq 1 "$N"); do ORD+=("$(cont $i)"); done
log(){ echo "[$(date +%H:%M:%S)] $*" | tee -a "$OUT/run.log"; }

leader_now(){
  local id v
  for id in $(seq 1 "$N"); do
    v=$(curl -s --max-time 2 "localhost:$(opsport "$id")/metrics" 2>/dev/null \
        | grep -E '^consensus_etcdraft_is_leader' | grep -oE '[01]$' | head -1)
    [ "$v" = "1" ] && { echo "$id"; return; }
  done
  echo 0
}
bl_of_file(){ grep -oE '"blacklist" *: *\[[0-9, ]*\]' "$1" 2>/dev/null | grep -oE '[0-9]+' | tr '\n' ' '; }
# What the ORDERER actually holds, not what we think we pushed.  Reads the first
# RUNNING orderer other than <skip>: a forced election pauses the incumbent, and
# `docker exec` into a paused container fails, which is how the first attempt
# recorded an empty delivery column for every single election.  Commas are
# stripped because this lands in a CSV field.
advice_on_orderer(){
  local skip="${1:-0}" id st out
  for id in $(seq 1 "$N"); do
    [ "$id" = "$skip" ] && continue
    st=$(docker inspect -f '{{.State.Status}}' "$(cont "$id")" 2>/dev/null)
    [ "$st" = "running" ] || continue
    out=$(docker exec "$(cont "$id")" cat /tmp/bora-advice.json 2>/dev/null | tr -d '\n' | tr ',' ';')
    [ -n "$out" ] && { echo "n${id}:${out}"; return; }
  done
  echo "UNREADABLE"
}

set_all(){ for o in "${ORD[@]}"; do
  docker exec "$o" sh -c "printf '%s' '{\"blacklist\":$1,\"seq\":1,\"fail_open\":false}' > /tmp/bora-advice.json" 2>/dev/null
done; }
leader_watch(){
  ( while [ -f /tmp/r13.on ]; do leader_now > /tmp/r13.leader.tmp 2>/dev/null; mv -f /tmp/r13.leader.tmp /tmp/r13.leader 2>/dev/null; sleep 2; done ) >/dev/null 2>&1 & WATCHPID=$!; }
push_empty(){ ( while [ -f /tmp/r13.on ]; do set_all "[]"; sleep 0.5; done ) >/dev/null 2>&1 & PUSHPID=$!; }
push_from(){ local src="$1"
  ( while [ -f /tmp/r13.on ]; do
      bl=$(grep -oE '"blacklist" *: *\[[0-9, ]*\]' "$src" 2>/dev/null | grep -oE '\[[0-9, ]*\]' | tr -d ' ')
      [ -n "$bl" ] && set_all "$bl"; sleep 0.3
    done ) >/dev/null 2>&1 & PUSHPID=$!; }

# Authority actuator.  Stands down while a forced election is in flight so the
# two pause mechanisms never fight over the same container.
authority_loop(){ local logf="$1"
  ( while [ -f /tmp/r13.on ]; do
      [ -f /tmp/r13.busy ] && { sleep 0.5; continue; }
      bl=$(bl_of_file "$BTFP"); [ -z "$bl" ] && { sleep 0.5; continue; }
      L=$(leader_now)
      if [ "$L" != 0 ] && printf ' %s ' "$bl" | grep -q " $L "; then
        tset=$(grep -oE '"true" *: *\[[0-9, ]*\]' "$BTFP" 2>/dev/null | grep -oE '[0-9]+' | tr '\n' ' ')
        cause=FP; printf ' %s ' "$tset" | grep -q " $L " && cause=TP
        echo "$(date +%s.%N) demote leader=$L cause=$cause bl=[$bl] true=[$tset]" >> "$logf"
        docker pause "$(cont "$L")" >/dev/null 2>&1; sleep 9
        docker unpause "$(cont "$L")" >/dev/null 2>&1; sleep 4
      fi
      sleep 0.5
    done ) >/dev/null 2>&1 & AUTHPID=$!; }

# ------------------------------------------------------------ forced election
# Identical mechanism and cadence in all three arms, so the arms differ only in
# what the advice does -- not in how often the cluster is disturbed.
force_election(){   # <cell dir> <index>
  local cdir="$1" idx="$2" L NL bl adv fpn won live delivered
  L=$(leader_now); [ "$L" = 0 ] && { echo "$idx,-,-,-,-,-,-,-,noleader" >> "$cdir/elections.csv"; return; }
  bl=$(bl_of_file "$BTFP")
  adv=$(advice_on_orderer "$L")
  # the flagged HEALTHY node (a false positive), if any is in force right now
  fpn=$(printf '%s' "$bl" | tr ' ' '\n' | grep -vx "$TARGET" | grep -E '^[0-9]+$' | head -1)
  # Did the advice the ORDERER is actually holding contain that node?  This is
  # the whole point of the column: without it, "arm C changed nothing" cannot be
  # told apart from "arm C was never told anything".
  delivered=0
  [ -n "$fpn" ] && printf '%s' "$adv" | grep -qE "\[[0-9;]*${fpn}[];]" && delivered=1
  touch /tmp/r13.busy
  docker pause "$(cont "$L")" >/dev/null 2>&1
  # Poll instead of reading once at t+9s.  A single read cannot tell "the
  # election failed" from "the election was slower than my window", and the
  # first version of this reported four liveness failures in arm C purely
  # because the guard's smaller candidate set needed longer than nine seconds.
  # Time-to-leader is the honest quantity, and it is also the one that compares
  # the interfaces: authority pays it on every wrong prediction.
  local waited=0 ttl=-1
  NL=0
  while [ "$waited" -lt 25 ]; do
    sleep 2; waited=$(( waited + 2 ))
    NL=$(leader_now)
    [ "$NL" != 0 ] && [ "$NL" != "$L" ] && { ttl=$waited; break; }
  done
  docker unpause "$(cont "$L")" >/dev/null 2>&1
  sleep 4
  rm -f /tmp/r13.busy
  live=1; [ "$NL" = 0 ] && live=0
  won=0; [ -n "$fpn" ] && [ "$NL" = "$fpn" ] && won=1
  echo "$idx,$L,$NL,${fpn:--},$won,$live,$ttl,$delivered,$adv" >> "$cdir/elections.csv"
}

# ------------------------------------------------------------ one cell
cell(){
  local arm="$1" rate="$2" seed="$3"
  local tag="${arm}_p${rate}_s${seed}" cdir
  cdir="$OUT/$tag"; mkdir -p "$cdir"
  echo "idx,leader_before,leader_after,fp_node,fp_node_won,live,time_to_leader_s,fp_delivered,advice_seen_on" > "$cdir/elections.csv"
  log "cell $tag (dur=${DUR}s, election every ${ELEC_EVERY}s)"

  set_all "[]"; rm -f "$BTFP" /tmp/r13.busy /tmp/r13.leader; touch /tmp/r13.on
  local WATCHPID=""; leader_watch; sleep 3
  local since; since=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  leader_now > "$cdir/leader0.txt"

  python3 "$D/alg1/r13_fp_inject.py" --rate "$rate" --seed "$seed" --dur "$DUR" \
      --n "$N" --target "$TARGET" --cap "$CAP" --hold 20 --leader-file /tmp/r13.leader --src "$BT" --out "$BTFP" \
      --log "$cdir/fp.log" >/dev/null 2>"$cdir/fp.err" &
  local FPPID=$!
  python3 "$D/alg1/r13_fp_inject.py" --rate "$rate" --seed "$seed" --dur "$DUR" \
      --n "$N" --target "$TARGET" --cap "$CAP" --hold 20 --dump-schedule > "$cdir/schedule.csv" 2>/dev/null
  sleep 3
  if [ ! -s "$BTFP" ]; then
    log "GATE FAIL: injector wrote no advice"; [ -s "$cdir/fp.err" ] && tail -3 "$cdir/fp.err" | tee -a "$OUT/run.log"
    rm -f /tmp/r13.on; kill "$FPPID" 2>/dev/null; exit 1
  fi

  local PUSHPID="" AUTHPID=""
  case "$arm" in
    A) push_empty ;;
    C) push_from "$BTFP" ;;
    D) push_empty; authority_loop "$cdir/authority.log" ;;
  esac
  log "  arm=$arm push=$PUSHPID auth=${AUTHPID:-none}"

  local t=0 i=0
  while [ "$t" -lt "$DUR" ]; do
    sleep "$ELEC_EVERY"; t=$(( t + ELEC_EVERY )); i=$(( i + 1 ))
    force_election "$cdir" "$i"
  done

  rm -f /tmp/r13.on /tmp/r13.busy; sleep 2
  kill "$FPPID" "$PUSHPID" "$WATCHPID" $AUTHPID 2>/dev/null || true
  set_all "[]"

  for id in $(seq 1 "$N"); do docker logs --timestamps --since "$since" "$(cont $id)" 2>&1 \
    | grep -aE 'Raft leader changed: [0-9]+ -> [0-9]+' \
    | sed -E 's/^([^ ]+) .*Raft leader changed: ([0-9]+) -> ([0-9]+).*/\1 \2 \3/'; done | sort -u > "$cdir/leader_changes.txt"

  local M; M=$(python3 "$D/alg1/r13_metrics.py" "$cdir" "$N" "$TARGET" "$DUR")
  local LC rest; LC=${M%%,*}
  local EL EWF FPW LF AS
  EL=$(( $(wc -l < "$cdir/elections.csv") - 1 ))
  EWF=$(awk -F, 'NR>1 && $4!="-"' "$cdir/elections.csv" | wc -l)
  FPW=$(awk -F, 'NR>1 && $5==1' "$cdir/elections.csv" | wc -l)
  LF=$(awk -F, 'NR>1 && $6==0' "$cdir/elections.csv" | wc -l)
  # how many elections saw a NON-EMPTY blacklist actually sitting on orderer1
  # column 8, not 7: inserting time_to_leader_s shifted fp_delivered right, and
  # the summary then reported advice_seen=0 while every row carried delivered=1.
  AS=$(awk -F, 'NR>1 && $8==1' "$cdir/elections.csv" | wc -l)
  local DEM=0 DTP=0 DFP=0
  if [ -f "$cdir/authority.log" ]; then
    DEM=$(grep -c ' demote ' "$cdir/authority.log" || true)
    DTP=$(grep -c 'cause=TP' "$cdir/authority.log" || true)
    DFP=$(grep -c 'cause=FP' "$cdir/authority.log" || true)
  fi
  local TTL
  TTL=$(awk -F, 'NR>1 && $7>=0 {s+=$7; n++} END{if(n) printf "%.1f", s/n; else print "-"}' "$cdir/elections.csv")
  local SV=0
  for o in "${ORD[@]}"; do SV=$((SV + $(docker logs --since "$since" "$o" 2>&1 | grep -acE 'PANI|FATAL' || true))); done

  echo "$arm,$rate,$seed,$DUR,$EL,$EWF,$FPW,$LC,$DEM,$DTP,$DFP,$LF,$TTL,$AS,$SV" >> "$OUT/cells.csv"
  log "  -> elec=$EL with_fp=$EWF fp_won=$FPW changes=$LC demote=$DEM(TP=$DTP FP=$DFP) livefail=$LF ttl=${TTL}s advice_seen=$AS safety=$SV"
}

# ------------------------------------------------------------ shared setup
FEED="$D/results/rtt_feed.csv"
start_probe(){ docker rm -f rtt-probe >/dev/null 2>&1; rm -f "$FEED"
  docker run -d --name rtt-probe --network fabric_test -v /mnt/d/fabric-d2:/feed \
    -v "$D/alg1/rtt_probe_n.py:/rtt_probe.py" -e FEED=/feed/results/rtt_feed.csv -e N="$N" \
    python:3.11-slim python /rtt_probe.py >/dev/null 2>&1; }
stop_attack(){ docker stop -t 15 pumba-r13 >/dev/null 2>&1; docker rm -f pumba-r13 >/dev/null 2>&1; }
qdisc_of(){ docker run --rm --net="container:$1" --cap-add=NET_ADMIN gaiadocker/iproute2 qdisc show dev eth0 2>/dev/null | head -1; }
start_attack(){
  stop_attack; sleep 3
  case "$(qdisc_of "$(cont $TARGET)")" in *netem*) log "GATE FAIL: residual netem on target"; exit 1;; esac
  docker run -d --name pumba-r13 -v /var/run/docker.sock:/var/run/docker.sock gaiaadm/pumba:latest \
    --log-level warning netem --tc-image gaiadocker/iproute2 --duration 600m \
    delay --time 200 "$(cont $TARGET)" >/dev/null 2>&1
  sleep 8
  docker logs pumba-r13 2>&1 | grep -q 'level=fatal' && { log "GATE FAIL: pumba fatal"; exit 1; }
  case "$(qdisc_of "$(cont $TARGET)")" in *netem*) log "  attack OK";; *) log "GATE FAIL: no netem on target"; exit 1;; esac; }
check_attack(){ docker ps --format '{{.Names}}' | grep -q '^pumba-r13$' || { log "GATE FAIL: pumba gone"; exit 1; }; }
gate_daemon(){
  [ -f "$BT" ] || { log "GATE FAIL: bt.json missing"; exit 1; }
  local age; age=$(( $(date +%s) - $(stat -c %Y "$BT") ))
  [ "$age" -le 15 ] || { log "GATE FAIL: bt.json ${age}s stale"; exit 1; }; }

log "R1-3 v2  N=$N f=$F cap=$CAP seeds=$SEEDS dur=$DUR rates=${RATES[*]} elec_every=$ELEC_EVERY"
log "OUT=$OUT"
start_probe; start_attack; sleep 20
bash "$D/alg1/start_daemon.sh" "$N" "$F" | tee -a "$OUT/run.log"
sleep 25; gate_daemon; check_attack

# ------------------------------------------------------------ calibration
# Which healthy orderer actually wins elections here?  Leadership is not uniform
# on this testbed, so a false positive aimed at a node that never wins tests
# nothing: arm A and arm C both report zero and the control is vacuous.  Six
# advice-free forced elections identify the front-runner, and every arm then
# aims its false positives at that same node -- fixed across arms, so the
# comparison stays paired.
mkdir -p "$OUT/calib"
echo "idx,leader_before,leader_after,fp_node,fp_node_won,live,time_to_leader_s,fp_delivered,advice_seen_on" > "$OUT/calib/elections.csv"
set_all "[]"; rm -f "$BTFP"; : > "$BTFP"
FRONT=0
log "calibration: 6 advice-free forced elections"
for i in $(seq 1 6); do force_election "$OUT/calib" "$i"; done
FRONT=$(awk -F, 'NR>1 && $3 ~ /^[0-9]+$/ && $3 != 0 {print $3}' "$OUT/calib/elections.csv" \
        | grep -vx "$TARGET" | sort | uniq -c | sort -rn | head -1 | awk '{print $2}')
[ -n "$FRONT" ] && [ "$FRONT" != 0 ] || { log "GATE FAIL: calibration found no front-runner"; exit 1; }
log "  front-runner = orderer$FRONT (false positives will name it in every arm)"
awk -F, 'NR>1{print "    calib elec "$1": "$2" -> "$3}' "$OUT/calib/elections.csv" | tee -a "$OUT/run.log"
for rate in "${RATES[@]}"; do
  for seed in $(seq 1 "$SEEDS"); do
    for arm in A C D; do check_attack; gate_daemon; cell "$arm" "$rate" "$seed"; done
  done
done
stop_attack; docker rm -f rtt-probe >/dev/null 2>&1
log "netem after teardown: $(qdisc_of "$(cont $TARGET)")"
log "done -> $OUT/cells.csv"
column -s, -t < "$OUT/cells.csv" | tee -a "$OUT/run.log"
