#!/usr/bin/env bash
# R1-3, third design.  Two things v2 got wrong and one it could not measure.
#
# WHAT CHANGED AND WHY
#
# 1. ARM D IS NO LONGER A STRAWMAN.  v2's authority arm was "demote whoever the
#    detector names", with the guard switched off.  An interface defined to
#    demote will demote, so the headline contrast was partly definitional, and
#    the arm also let the degraded node take office in a way no real
#    learning-augmented system would.  Arm D is now BORA MINUS THE ACTIVE-LEADER
#    RULE: same detector, same blacklist, same cap, same fail-open, same guard --
#    the incumbent simply loses its exemption.  C and D then differ in exactly
#    one design decision, the one the paper argues for, so this is an ablation of
#    our own claim rather than a contest with a weaker opponent.
#
# 2. COST IS MEASURED, NOT COUNTED.  "How many times did the leader move" follows
#    from each arm's definition.  "How many seconds was the channel without a
#    leader" does not: it is what the moves actually cost, and the leader sampler
#    records it directly.  A ledger-throughput figure would be better still, but
#    no chaincode is deployed on this cluster and standing one up has a long
#    history of failure here, so leaderless time is the honest available proxy.
#
# 3. THE ARTIFACT THAT FAKED A LIVENESS FINDING IS GATED.  v2 reported exactly
#    three failed elections in seven different cells -- always the last three --
#    because a container had been left paused and never recovered.  Every cell
#    now starts with a health check that unpauses, restores sidecars and confirms
#    a leader, and records whether repair was needed.
#
# Phase 2 measures what ALR costs rather than what it saves: the degraded node is
# seated as leader first, and we time how long each arm leaves it there.
#
#   r13_v3.sh <N> <seeds> <dur_s> [rates...]
set -u
N="${1:?need N}"; SEEDS="${2:-3}"; DUR="${3:-300}"
if [ $# -gt 3 ]; then shift 3; RATES=("$@"); else RATES=(0 5 10 20); fi
F=$(( (N - 1) / 2 ))
CAP=$(( F - 1 ))
TARGET=3
ELEC_EVERY=30
D=/mnt/d/fabric-d2
BT="$D/results/bt.json"
BTFP="$D/results/bt_r13.json"
export PATH=/tmp/bin:"$D"/fabric-samples/bin-linux/bin:/usr/local/bin:/usr/bin:/bin:/mnt/c/WINDOWS/System32/WindowsPowerShell/v1.0

OUT="$D/results/r13v3_N${N}_$(date +%m%d-%H%M%S)"; mkdir -p "$OUT"
echo "phase,arm,rate,seed,dur,elections,elec_with_fp,leader_changes,demotions,demote_TP,demote_FP,leaderless_s,target_tenure_s,liveness_fail,mean_ttl_s,advice_seen,repaired,safety_viol" \
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
advice_on_orderer(){
  local skip="${1:-0}" id st out
  for id in $(seq 1 "$N"); do
    [ "$id" = "$skip" ] && continue
    st=$(docker inspect -f '{{.State.Status}}' "$(cont "$id")" 2>/dev/null)
    [ "$st" = "running" ] || continue
    out=$(docker exec "$(cont "$id")" cat /tmp/bora-advice.json 2>/dev/null | tr -d '\n' | tr ',' ';')
    [ -n "$out" ] && { echo "n${id}:${out}"; return; }
  done
  echo UNREADABLE
}
set_all(){ for o in "${ORD[@]}"; do
  docker exec "$o" sh -c "printf '%s' '{\"blacklist\":$1,\"seq\":1,\"fail_open\":false}' > /tmp/bora-advice.json" 2>/dev/null
done; }

# ------------------------------------------------------------ health check
# The cell-level gate that v2 lacked.  Returns the number of repairs it had to
# make; a run where this keeps rising is a run whose cluster is degrading, and
# that is worth seeing in the data rather than discovering afterwards.
health_check(){
  local fixed=0 id c st
  for id in $(seq 1 "$N"); do
    c=$(cont "$id")
    st=$(docker inspect -f '{{.State.Status}}' "$c" 2>/dev/null)
    if [ "$st" = "paused" ]; then docker unpause "$c" >/dev/null 2>&1; fixed=$((fixed+1)); sleep 3; fi
    if [ "$st" = "exited" ]; then docker start "$c" >/dev/null 2>&1; fixed=$((fixed+1)); sleep 8; fi
    docker exec "$c" sh -c 'cat /proc/[0-9]*/comm 2>/dev/null | grep -q "^bora-sidecar$" || { rm -f /var/run/raft-advisor.sock; setsid /tmp/bora-sidecar >/tmp/bs.log 2>&1 </dev/null; }' 2>/dev/null || true
  done
  local L tries=0
  L=$(leader_now)
  while [ "$L" = 0 ] && [ "$tries" -lt 10 ]; do sleep 3; tries=$((tries+1)); L=$(leader_now); done
  [ "$L" = 0 ] && { log "  HEALTH FAIL: no leader after repair"; return 99; }
  echo "$fixed" > /tmp/r13.repaired
  return 0
}

# ------------------------------------------------------------ samplers
leader_watch(){   # <cell dir> — 2 s samples; leaderless time comes from these
  local cdir="$1"
  ( while [ -f /tmp/r13.on ]; do
      printf '%s,%s\n' "$(date +%s)" "$(leader_now)" >> "$cdir/leader_samples.csv"
      sleep 2
    done ) >/dev/null 2>&1 & WATCHPID=$!
}
push_empty(){ ( while [ -f /tmp/r13.on ]; do set_all "[]"; sleep 0.5; done ) >/dev/null 2>&1 & PUSHPID=$!; }
push_from(){ local src="$1"
  ( while [ -f /tmp/r13.on ]; do
      bl=$(grep -oE '"blacklist" *: *\[[0-9, ]*\]' "$src" 2>/dev/null | grep -oE '\[[0-9, ]*\]' | tr -d ' ')
      [ -n "$bl" ] && set_all "$bl"; sleep 0.3
    done ) >/dev/null 2>&1 & PUSHPID=$!; }

# Arm D's only difference from arm C: the incumbent has no exemption, so when the
# advice names it, it goes.  Fabric exposes no TransferLeadership on this build,
# so the demotion is a pause -- which is also the only demotion an operator could
# actually perform here, and we say so rather than pretending otherwise.
noalr_loop(){ local logf="$1"
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
    done ) >/dev/null 2>&1 & AUTHPID=$!
}

force_election(){   # <cell dir> <index>
  local cdir="$1" idx="$2" L NL bl adv fpn live delivered waited ttl
  L=$(leader_now); [ "$L" = 0 ] && { echo "$idx,-,-,-,-,-,-,noleader" >> "$cdir/elections.csv"; return; }
  bl=$(bl_of_file "$BTFP"); adv=$(advice_on_orderer "$L")
  fpn=$(printf '%s' "$bl" | tr ' ' '\n' | grep -vx "$TARGET" | grep -E '^[0-9]+$' | head -1)
  delivered=0
  [ -n "$fpn" ] && printf '%s' "$adv" | grep -qE "\[[0-9;]*${fpn}[];]" && delivered=1
  touch /tmp/r13.busy
  docker pause "$(cont "$L")" >/dev/null 2>&1
  waited=0; ttl=-1; NL=0
  while [ "$waited" -lt 25 ]; do
    sleep 2; waited=$(( waited + 2 )); NL=$(leader_now)
    [ "$NL" != 0 ] && [ "$NL" != "$L" ] && { ttl=$waited; break; }
  done
  docker unpause "$(cont "$L")" >/dev/null 2>&1; sleep 4
  rm -f /tmp/r13.busy
  live=1; [ "$NL" = 0 ] && live=0
  echo "$idx,$L,$NL,${fpn:--},$live,$ttl,$delivered,$adv" >> "$cdir/elections.csv"
}

# Seat the degraded orderer as leader, guard inert, so phase 2 can time how long
# each arm leaves it there.
seat_target(){
  # The degraded node is HARDER to seat than any other, for the same reason the
  # paper reports it winning at 0.42-1.00x its chance share: +200 ms slows its
  # vote exchange.  Twelve blind retries failed roughly a third of the time.
  # Two changes: more attempts, and narrowing the field.  During seating only,
  # the two most recent winners are pushed as advice so the guard keeps them out
  # of the running, which cuts the candidate pool from six to four.  The advice
  # is cleared before any measurement begins, so the measured window is unaffected.
  local tries=0 L prev1="" prev2="" bl
  set_all "[]"; sleep 1
  L=$(leader_now)
  while [ "$L" != "$TARGET" ] && [ "$tries" -lt 30 ]; do
    tries=$((tries+1))
    if [ "$L" != 0 ] && [ "$L" != "$TARGET" ]; then
      prev2="$prev1"; prev1="$L"
      bl="[$prev1"; [ -n "$prev2" ] && [ "$prev2" != "$prev1" ] && bl="$bl,$prev2"; bl="$bl]"
      set_all "$bl"
      docker pause "$(cont "$L")" >/dev/null 2>&1; sleep 9
      docker unpause "$(cont "$L")" >/dev/null 2>&1; sleep 4
    fi
    L=$(leader_now)
  done
  set_all "[]"; sleep 1
  echo "$tries" > /tmp/r13.seattries
  [ "$L" = "$TARGET" ] && return 0 || return 1
}

# ------------------------------------------------------------ one cell
cell(){   # <phase> <arm> <rate> <seed> <dur> [seat]
  local phase="$1" arm="$2" rate="$3" seed="$4" dur="$5" seat="${6:-0}"
  local tag="${phase}_${arm}_p${rate}_s${seed}" cdir
  cdir="$OUT/$tag"; mkdir -p "$cdir"
  echo "idx,leader_before,leader_after,fp_node,live,time_to_leader_s,fp_delivered,advice_seen_on" > "$cdir/elections.csv"
  : > "$cdir/leader_samples.csv"

  health_check || { log "  SKIP $tag (health)"; return; }
  local REP; REP=$(cat /tmp/r13.repaired 2>/dev/null || echo 0)
  log "cell $tag (dur=${dur}s, repaired=$REP)"

  if [ "$seat" = 1 ]; then
    if seat_target; then
      log "  target orderer$TARGET seated after $(cat /tmp/r13.seattries 2>/dev/null) attempts"
    else
      log "  SKIP $tag (could not seat target in $(cat /tmp/r13.seattries 2>/dev/null) attempts)"
      echo "$phase,$arm,$rate,$seed,$dur,-,-,-,-,-,-,-,-,-,-,-,$REP,SEAT_FAIL" >> "$OUT/cells.csv"
      return
    fi
  fi

  set_all "[]"; rm -f "$BTFP" /tmp/r13.busy /tmp/r13.leader; touch /tmp/r13.on
  local since; since=$(date -u +%Y-%m-%dT%H:%M:%SZ)
  local WATCHPID=""; leader_watch "$cdir"; sleep 3

  python3 "$D/alg1/r13_fp_inject.py" --rate "$rate" --seed "$seed" --dur "$dur" \
      --n "$N" --target "$TARGET" --cap "$CAP" --hold 20 --leader-file /tmp/r13.leader \
      --src "$BT" --out "$BTFP" --log "$cdir/fp.log" >/dev/null 2>"$cdir/fp.err" &
  local FPPID=$!
  ( while [ -f /tmp/r13.on ]; do leader_now > /tmp/r13.leader.tmp 2>/dev/null; mv -f /tmp/r13.leader.tmp /tmp/r13.leader 2>/dev/null; sleep 2; done ) >/dev/null 2>&1 &
  local LPID=$!
  sleep 3
  [ -s "$BTFP" ] || { log "  GATE FAIL: injector silent"; tail -2 "$cdir/fp.err" 2>/dev/null | tee -a "$OUT/run.log"; rm -f /tmp/r13.on; kill "$FPPID" "$WATCHPID" "$LPID" 2>/dev/null; exit 1; }

  local PUSHPID="" AUTHPID=""
  case "$arm" in
    A) push_empty ;;
    C) push_from "$BTFP" ;;
    D) push_from "$BTFP"; noalr_loop "$cdir/demote.log" ;;
  esac

  local t=0 i=0
  while [ "$t" -lt "$dur" ]; do
    sleep "$ELEC_EVERY"; t=$(( t + ELEC_EVERY ))
    if [ "$seat" != 1 ]; then i=$(( i + 1 )); force_election "$cdir" "$i"; fi
  done

  rm -f /tmp/r13.on /tmp/r13.busy; sleep 2
  kill "$FPPID" "$PUSHPID" "$WATCHPID" "$LPID" $AUTHPID 2>/dev/null || true
  set_all "[]"

  for id in $(seq 1 "$N"); do docker logs --timestamps --since "$since" "$(cont $id)" 2>&1 \
    | grep -aE 'Raft leader changed: [0-9]+ -> [0-9]+' \
    | sed -E 's/^([^ ]+) .*Raft leader changed: ([0-9]+) -> ([0-9]+).*/\1 \2 \3/'; done | sort -u > "$cdir/leader_changes.txt"

  local LC EL EWF LF AS TTL DEM DTP DFP LESS TEN SV
  LC=$(python3 "$D/alg1/r13_metrics.py" "$cdir" "$N" "$TARGET" "$dur" 2>/dev/null | cut -d, -f1); LC=${LC:-0}
  EL=$(( $(wc -l < "$cdir/elections.csv") - 1 ))
  EWF=$(awk -F, 'NR>1 && $4!="-"' "$cdir/elections.csv" | wc -l)
  LF=$(awk -F, 'NR>1 && $5==0' "$cdir/elections.csv" | wc -l)
  AS=$(awk -F, 'NR>1 && $7==1' "$cdir/elections.csv" | wc -l)
  TTL=$(awk -F, 'NR>1 && $6>=0 {s+=$6; n++} END{if(n) printf "%.1f", s/n; else print "-"}' "$cdir/elections.csv")
  # leaderless and target-tenure come from the 2 s sampler, not from definitions
  LESS=$(awk -F, '$2==0{n++} END{print (n+0)*2}' "$cdir/leader_samples.csv")
  TEN=$(awk -F, -v t="$TARGET" '$2==t{n++} END{print (n+0)*2}' "$cdir/leader_samples.csv")
  DEM=0; DTP=0; DFP=0
  if [ -f "$cdir/demote.log" ]; then
    DEM=$(grep -c ' demote ' "$cdir/demote.log" || true)
    DTP=$(grep -c 'cause=TP' "$cdir/demote.log" || true)
    DFP=$(grep -c 'cause=FP' "$cdir/demote.log" || true)
  fi
  SV=0; for o in "${ORD[@]}"; do SV=$((SV + $(docker logs --since "$since" "$o" 2>&1 | grep -acE 'PANI|FATAL' || true))); done

  echo "$phase,$arm,$rate,$seed,$dur,$EL,$EWF,$LC,$DEM,$DTP,$DFP,$LESS,$TEN,$LF,$TTL,$AS,$REP,$SV" >> "$OUT/cells.csv"
  log "  -> elec=$EL fp=$EWF changes=$LC demote=$DEM(TP=$DTP FP=$DFP) leaderless=${LESS}s tenure=${TEN}s livefail=$LF ttl=${TTL}s adv=$AS rep=$REP safety=$SV"
}

# ------------------------------------------------------------ setup
FEED="$D/results/rtt_feed.csv"
start_probe(){ docker rm -f rtt-probe >/dev/null 2>&1; rm -f "$FEED"
  docker run -d --name rtt-probe --network fabric_test -v /mnt/d/fabric-d2:/feed \
    -v "$D/alg1/rtt_probe_n.py:/rtt_probe.py" -e FEED=/feed/results/rtt_feed.csv -e N="$N" \
    python:3.11-slim python /rtt_probe.py >/dev/null 2>&1; }
stop_attack(){ docker stop -t 15 pumba-r13 >/dev/null 2>&1; docker rm -f pumba-r13 >/dev/null 2>&1; }
qdisc_of(){ docker run --rm --net="container:$1" --cap-add=NET_ADMIN gaiadocker/iproute2 qdisc show dev eth0 2>/dev/null | head -1; }
start_attack(){
  stop_attack; sleep 3
  case "$(qdisc_of "$(cont $TARGET)")" in *netem*) log "GATE FAIL: residual netem"; exit 1;; esac
  docker run -d --name pumba-r13 -v /var/run/docker.sock:/var/run/docker.sock gaiaadm/pumba:latest \
    --log-level warning netem --tc-image gaiadocker/iproute2 --duration 600m \
    delay --time 200 "$(cont $TARGET)" >/dev/null 2>&1
  sleep 8
  docker logs pumba-r13 2>&1 | grep -q 'level=fatal' && { log "GATE FAIL: pumba fatal"; exit 1; }
  case "$(qdisc_of "$(cont $TARGET)")" in *netem*) log "  attack OK";; *) log "GATE FAIL: no netem"; exit 1;; esac; }
check_attack(){ docker ps --format '{{.Names}}' | grep -q '^pumba-r13$' || { log "GATE FAIL: pumba gone"; exit 1; }; }
gate_daemon(){ [ -f "$BT" ] || { log "GATE FAIL: bt.json missing"; exit 1; }
  local age; age=$(( $(date +%s) - $(stat -c %Y "$BT") ))
  [ "$age" -le 15 ] || { log "GATE FAIL: bt.json ${age}s stale"; exit 1; }; }

log "R1-3 v3  N=$N f=$F cap=$CAP seeds=$SEEDS dur=$DUR rates=${RATES[*]}"
log "  arm D = BORA minus the Active-Leader Rule (ablation, not a strawman)"
log "OUT=$OUT"
start_probe; start_attack; sleep 20
bash "$D/alg1/start_daemon.sh" "$N" "$F" | tee -a "$OUT/run.log"
sleep 25; gate_daemon; check_attack

# Phase 1 -- arm order rotates per block so run drift is shared, not assigned
b=0
for rate in "${RATES[@]}"; do
  for seed in $(seq 1 "$SEEDS"); do
    b=$(( b + 1 ))
    case $(( b % 3 )) in
      0) ORDER="A C D";; 1) ORDER="C D A";; 2) ORDER="D A C";;
    esac
    for arm in $ORDER; do check_attack; gate_daemon; cell P1 "$arm" "$rate" "$seed" "$DUR" 0; done
  done
done

# Phase 2 -- what ALR costs: seat the degraded node, then time its tenure
log "Phase 2: degraded incumbent, tenure under C vs D"
for seed in $(seq 1 "$SEEDS"); do
  for arm in C D; do check_attack; gate_daemon; cell P2 "$arm" 0 "$seed" 180 1; done
done

stop_attack; docker rm -f rtt-probe >/dev/null 2>&1
log "netem after teardown: $(qdisc_of "$(cont $TARGET)")"
log "done -> $OUT/cells.csv"
column -s, -t < "$OUT/cells.csv" | tee -a "$OUT/run.log"
