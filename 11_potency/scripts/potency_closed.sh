#!/usr/bin/env bash
# Closed-loop arm: the blacklist comes from the detector, not from the operator.
#
# potency_run.sh's guarded arm sets the advice to [3] directly, so it returned
# 0/40 in every condition -- including the ones the detector cannot see.  That
# measures whether the exclusion mechanism works, not whether detection drives
# it.  Here nothing writes the blacklist by hand: an in-network probe feeds RTT,
# the daemon scores it with the same checkpoint the white-box attack was
# computed against, and the pusher injects whatever the daemon emits.
#
# Runs at the benchmark's own 8 ms scale.  The window builder derives a feature
# from (RTT <= 100 ms), which is true throughout training; on the 500 ms tracks
# it is false throughout, so the detector would be scoring input unlike anything
# it has seen and the arm would come out flat for reasons unrelated to evasion.
#
# Usage:  potency_closed.sh [N]
set -u

N="${1:-40}"
SCALE=m8
TARGET=3
N_ORD=7
TICK=0.15

export N_ORD
source /d/fabric-d2/alg1/sidecar_lib.sh

R=/d/fabric-d2/results
TRACKS=$R/potency
PANEL="/d/프랑스 업데이트/TNSE 스페셜이슈 논문/experiments/08_predictor/r12_panel"
OUT="$TRACKS/closed_${SCALE}_$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT"

CONDS="healthy_white pgd_rho_0.0 pgd_rho_0.3 pgd_rho_0.6 pgd_rho_0.8 attack_class_ar1"

ord_name(){ if [ "$1" = 1 ]; then echo orderer.example.com; else echo "orderer$1.example.com"; fi; }

tc_up(){
  for i in $(seq 1 $N_ORD); do
    docker rm -f "tcc$i" >/dev/null 2>&1
    docker run -d --name "tcc$i" --net "container:$(ord_name $i)" --cap-add NET_ADMIN \
      --entrypoint sh gaiadocker/iproute2 -c "sleep 36000" >/dev/null 2>&1
  done
  sleep 3
}
tc_down(){
  for i in $(seq 1 $N_ORD); do
    docker exec "tcc$i" tc qdisc del dev eth0 root >/dev/null 2>&1
    docker rm -f "tcc$i" >/dev/null 2>&1
  done
}

replay(){
  local csv="$1"
  while [ -f "$STOP" ]; do
    while IFS=, read -r d1 d2 d3 d4 d5 d6 d7; do
      [ -f "$STOP" ] || break
      docker exec tcc1 tc qdisc replace dev eth0 root netem delay "${d1}ms" 2>/dev/null &
      docker exec tcc2 tc qdisc replace dev eth0 root netem delay "${d2}ms" 2>/dev/null &
      docker exec tcc3 tc qdisc replace dev eth0 root netem delay "${d3}ms" 2>/dev/null &
      docker exec tcc4 tc qdisc replace dev eth0 root netem delay "${d4}ms" 2>/dev/null &
      docker exec tcc5 tc qdisc replace dev eth0 root netem delay "${d5}ms" 2>/dev/null &
      docker exec tcc6 tc qdisc replace dev eth0 root netem delay "${d6}ms" 2>/dev/null &
      docker exec tcc7 tc qdisc replace dev eth0 root netem delay "${d7}ms" 2>/dev/null &
      wait
      sleep $TICK
    done < "$csv"
  done
}

leader_id(){
  # Deeper tail than the 300 lines the first version used.  These orderers log
  # Store ActiveNodes every two seconds and, with the probe attached, a stream of
  # TLS handshake errors as well, so an election line is pushed out of a shallow
  # window within minutes.
  local id tmp
  tmp=$(mktemp -d)
  for id in $(seq 1 $N_ORD); do
    ( docker logs --tail 20000 "$(ord_name $id)" 2>&1 \
        | grep -ao "became leader at term [0-9]*" | tail -1 \
        | grep -ao "[0-9]*$" > "$tmp/$id" ) &
  done
  wait
  local b=-1 bid=0 t
  for id in $(seq 1 $N_ORD); do
    t=$(cat "$tmp/$id" 2>/dev/null)
    [ -n "$t" ] && [ "$t" -gt "$b" ] && { b=$t; bid=$id; }
  done
  rm -rf "$tmp"
  echo "$bid"
}

# Which node to pause when the leader is not yet known.
#
# The first version defaulted to orderer1 every time.  Starting from an idle
# cluster no election line existed, so the leader was unknown, orderer1 was
# paused, orderer1 was not the leader, nothing happened, no line was written --
# and the next iteration was in exactly the same state.  All 200 elections
# recorded new_leader=0: the arm ran to completion having never once triggered
# an election, and nothing in the output said so except the liveness column.
#
# Cycling the candidate breaks that fixed point: within at most N attempts the
# real leader is paused, an election happens, the log line appears, and
# leader_id works from then on.
# NOT a function called through $(...).  Command substitution runs in a
# subshell, so the counter increment was discarded every time and the same node
# was paused for all 200 elections -- the `paused` column came out a solid
# column of 1s.  Assigning in the caller's own shell is the whole point here.
PROBE_NEXT=1

advisors_alive(){ local i c=0; for i in $(seq 1 $N_ORD); do sidecar_alive "$(ord_name $i)" && c=$((c+1)); done; echo "$c"; }

bt_now(){ grep -oE '"blacklist" *: *\[[0-9, ]*\]' "$R/bt.json" 2>/dev/null | grep -oE '\[[0-9, ]*\]' | tr -d ' '; }

# ---- start the loop: probe -> daemon -> pusher -----------------------------
echo "=== closed-loop: scale=$SCALE N=$N target=orderer$TARGET ===" | tee "$OUT/log.txt"
docker rm -f rtt-probe7 >/dev/null 2>&1
rm -f "$R/rtt_feed.csv"; echo '{"blacklist":[],"seq":1}' > "$R/bt.json"

MSYS_NO_PATHCONV=1 docker run -d --name rtt-probe7 --network fabric_test \
  -v /d/fabric-d2:/feed -v /d/fabric-d2/alg1/rtt_probe7.py:/rtt_probe7.py \
  -e FEED=/feed/results/rtt_feed.csv python:3.11-slim python /rtt_probe7.py >/dev/null 2>&1

ensure_all_sidecars
tc_up

( cd "$PANEL" && python closed_loop_daemon.py 0.01 90 ) > "$OUT/daemon.log" 2>&1 &
DAEMON=$!
RUN=/tmp/push7_$$.on
RUN=$RUN bash /d/fabric-d2/alg1/push_advice7.sh > "$OUT/pusher.log" 2>&1 &
PUSHER=$!

cleanup(){
  rm -f "$STOP" "$RUN" 2>/dev/null
  kill $DAEMON $PUSHER 2>/dev/null
  docker rm -f rtt-probe7 >/dev/null 2>&1
  for i in $(seq 1 $N_ORD); do docker exec "$(ord_name $i)" sh -c \
    "printf '%s' '{\"blacklist\":[],\"seq\":1,\"fail_open\":false}' > /tmp/bora-advice.json" 2>/dev/null; done
  tc_down
}
trap 'cleanup; exit 130' INT TERM

# The daemon calibrates its threshold on live telemetry, so this stretch must be
# attack-free: tc_up leaves the qdisc unset, and no track is replayed until the
# ready marker appears.  Calibrating against an attacked feed would raise the
# threshold to cover the attack and the detector would then never fire.
echo "  calibrating (attack-free) ..." | tee -a "$OUT/log.txt"
READY=/d/fabric-d2/results/daemon_ready
for _ in $(seq 1 240); do
  [ -f "$READY" ] && break
  sleep 1
done
if [ ! -f "$READY" ]; then
  echo "DAEMON_NOT_READY -- calibration never completed; aborting" | tee -a "$OUT/log.txt"
  sed -n '1,20p' "$OUT/daemon.log" | tee -a "$OUT/log.txt"
  cleanup
  exit 1
fi
echo "  threshold $(cat "$READY")" | tee -a "$OUT/log.txt"

echo "condition,election,prev_leader,paused,new_leader,target_won,live,advisors_alive,bt" > "$OUT/elections.csv"
echo "condition,wins,n,liveness,advisor_ok,bt_has_target,n_bt_samples" > "$OUT/summary.csv"

for c in $CONDS; do
  CSV="$TRACKS/${SCALE}_${c}.csv"
  [ -f "$CSV" ] || { echo "missing $CSV" | tee -a "$OUT/log.txt"; continue; }

  STOP="/tmp/closed_stop_$$"; touch "$STOP"
  replay "$CSV" & RP=$!
  sleep 25    # let the pattern fill the detector's window before measuring

  WINS=0; LIVE=0; ADVOK=0; BTHIT=0; BTN=0
  for k in $(seq 1 "$N"); do
    L=$(leader_id)
    if [ "$L" != 0 ]; then
      V=$L
    else
      V=$PROBE_NEXT
      PROBE_NEXT=$(( PROBE_NEXT % N_ORD + 1 ))
    fi
    LC=$(ord_name "$V")
    docker pause "$LC" >/dev/null 2>&1
    sleep 14
    NL=$(leader_id)
    docker unpause "$LC" >/dev/null 2>&1
    sleep 4
    AA=$(advisors_alive); BT=$(bt_now)
    BTN=$((BTN+1)); case "$BT" in *"$TARGET"*) BTHIT=$((BTHIT+1));; esac
    [ "$NL" = "$TARGET" ] && WINS=$((WINS+1))
    [ "$NL" != 0 ] && [ "$NL" != "$L" ] && LIVE=$((LIVE+1))
    [ "$AA" = "$N_ORD" ] && ADVOK=$((ADVOK+1))
    echo "$c,$k,$L,$V,$NL,$([ "$NL" = "$TARGET" ] && echo 1 || echo 0),$([ "$NL" != 0 ] && echo 1 || echo 0),$AA,\"$BT\"" \
      >> "$OUT/elections.csv"
  done

  rm -f "$STOP"; wait $RP 2>/dev/null
  echo "$c,$WINS,$N,$LIVE,$ADVOK,$BTHIT,$BTN" >> "$OUT/summary.csv"
  printf "  %-18s target %2d/%-2d  live %2d/%-2d  advisors %2d/%-2d  Bt∋o%d %2d/%-2d\n" \
    "$c" "$WINS" "$N" "$LIVE" "$N" "$ADVOK" "$N" "$TARGET" "$BTHIT" "$BTN" | tee -a "$OUT/log.txt"
done

cleanup
echo "CLOSED_DONE $OUT" | tee -a "$OUT/log.txt"
cat "$OUT/summary.csv" | tee -a "$OUT/log.txt"
