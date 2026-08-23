#!/usr/bin/env bash
# Does an evasive delay pattern still harm the ordering service?
#
# panel2 measured only whether each delay track was detected.  This measures
# what the same tracks do to the cluster: how often the targeted orderer wins
# leadership, and how many blocks the service commits, under each track.
#
# Forced elections use pause/unpause, not restart.  A restart recreates the
# orderer's network namespace, which takes the tc sidecar injecting the delay
# down with it -- the measurement would then run with no attack applied and
# report a clean cluster as evidence that the attack is harmless.
#
# Usage:  potency_run.sh <scale> <arm> [N]
#           scale = m8 | m500        arm = base | bora        N = elections/cond
set -u

SCALE="${1:?scale: m8 or m500}"
ARM="${2:?arm: base or bora}"
N="${3:-12}"
TARGET=3
N_ORD=7
TICK=0.15

# The guarded arm is only meaningful while the advisors are alive.  A dead
# sidecar makes the orderer fail open, which looks exactly like "BORA did not
# suppress anything" in the results -- the failure mode that invalidated every
# suppression measurement before the process-based check was introduced.  So the
# advisors are healed continuously and their liveness is recorded per election
# rather than assumed.
export N_ORD
source /d/fabric-d2/alg1/sidecar_lib.sh

TRACKS=/d/fabric-d2/results/potency
OUT="$TRACKS/run_${SCALE}_${ARM}_$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT"

CONDS="healthy_white pgd_rho_0.0 pgd_rho_0.3 pgd_rho_0.6 pgd_rho_0.8 attack_class_ar1"

ord_name(){ if [ "$1" = 1 ]; then echo orderer.example.com; else echo "orderer$1.example.com"; fi; }

# --- delay injection ------------------------------------------------------
tc_up(){
  for i in $(seq 1 $N_ORD); do
    docker rm -f "tcp$i" >/dev/null 2>&1
    docker run -d --name "tcp$i" --net "container:$(ord_name $i)" --cap-add NET_ADMIN \
      --entrypoint sh gaiadocker/iproute2 -c "sleep 36000" >/dev/null 2>&1
  done
  sleep 3
  for i in $(seq 1 $N_ORD); do
    docker exec "tcp$i" tc qdisc replace dev eth0 root netem delay 1ms >/dev/null 2>&1
  done
}
tc_down(){
  for i in $(seq 1 $N_ORD); do
    docker exec "tcp$i" tc qdisc del dev eth0 root >/dev/null 2>&1
    docker rm -f "tcp$i" >/dev/null 2>&1
  done
}

replay(){ # $1=csv ; loops until the stop flag clears
  local csv="$1" line
  while [ -f "$STOP" ]; do
    while IFS=, read -r d1 d2 d3 d4 d5 d6 d7; do
      [ -f "$STOP" ] || break
      docker exec tcp1 tc qdisc replace dev eth0 root netem delay "${d1}ms" 2>/dev/null &
      docker exec tcp2 tc qdisc replace dev eth0 root netem delay "${d2}ms" 2>/dev/null &
      docker exec tcp3 tc qdisc replace dev eth0 root netem delay "${d3}ms" 2>/dev/null &
      docker exec tcp4 tc qdisc replace dev eth0 root netem delay "${d4}ms" 2>/dev/null &
      docker exec tcp5 tc qdisc replace dev eth0 root netem delay "${d5}ms" 2>/dev/null &
      docker exec tcp6 tc qdisc replace dev eth0 root netem delay "${d6}ms" 2>/dev/null &
      docker exec tcp7 tc qdisc replace dev eth0 root netem delay "${d7}ms" 2>/dev/null &
      wait
      sleep $TICK
    done < "$csv"
  done
}

# --- cluster state --------------------------------------------------------
leader_id(){ # highest observed term wins; 0 if nothing reported
  # The seven log reads run concurrently.  Serially they cost about seven
  # seconds, and this is called twice per election, which at forty elections per
  # condition is over an hour of pure polling across the campaign.  It also sat
  # between the election and the unpause, so shortening it shortens the
  # intervention itself -- which is why runs recorded before this change are not
  # pooled with runs recorded after it.
  local id tmp
  tmp=$(mktemp -d)
  for id in $(seq 1 $N_ORD); do
    ( docker logs --tail 300 "$(ord_name $id)" 2>&1 \
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

height(){ # committed blocks on the peer's ledger
  docker exec peer0.org1.example.com peer channel getinfo -c mychannel 2>/dev/null \
    | grep -ao '"height":[0-9]*' | grep -ao '[0-9]*$'
}

set_advice(){ # $1 = json blacklist
  local i
  for i in $(seq 1 $N_ORD); do
    docker exec "$(ord_name $i)" sh -c \
      "printf '%s' '{\"blacklist\":$1,\"seq\":1,\"fail_open\":false}' > /tmp/bora-advice.json" 2>/dev/null
  done
}

# --- main -----------------------------------------------------------------
echo "condition,election,prev_leader,new_leader,target_won,live,advisors_alive" > "$OUT/elections.csv"
echo "condition,wins,n,liveness,advisor_ok,h0,h1,blocks,seconds,blocks_per_s" > "$OUT/summary.csv"

advisors_alive(){ # how many of the N orderers have a live bora-sidecar process
  local i c=0
  for i in $(seq 1 $N_ORD); do sidecar_alive "$(ord_name $i)" && c=$((c+1)); done
  echo "$c"
}

case "$ARM" in
  base) ADVICE="[]" ;;
  bora) ADVICE="[$TARGET]" ;;
  *) echo "arm must be base or bora"; exit 1 ;;
esac

echo "=== potency: scale=$SCALE arm=$ARM N=$N target=orderer$TARGET ===" | tee "$OUT/log.txt"
tc_up
trap 'rm -f "$STOP" 2>/dev/null; tc_down; exit 130' INT TERM

for c in $CONDS; do
  CSV="$TRACKS/${SCALE}_${c}.csv"
  [ -f "$CSV" ] || { echo "missing $CSV" | tee -a "$OUT/log.txt"; continue; }

  if [ "$ARM" = bora ]; then ensure_all_sidecars; fi
  set_advice "$ADVICE"
  STOP="/tmp/potency_stop_$$"; touch "$STOP"
  replay "$CSV" & RP=$!
  HEAL=""
  if [ "$ARM" = bora ]; then
    ( while [ -f "$STOP" ]; do ensure_all_sidecars; set_advice "$ADVICE"; sleep 1; done ) &
    HEAL=$!
  fi
  sleep 8                                    # let the pattern establish

  H0=$(height); T0=$(date +%s); WINS=0; LIVE=0; ADVOK=0
  for k in $(seq 1 "$N"); do
    L=$(leader_id); [ "$L" = 0 ] && L=1
    LC=$(ord_name "$L")
    docker pause "$LC" >/dev/null 2>&1
    sleep 14
    NL=$(leader_id)
    docker unpause "$LC" >/dev/null 2>&1
    sleep 4
    AA=$(advisors_alive)
    [ "$NL" = "$TARGET" ] && WINS=$((WINS+1))
    [ "$NL" != 0 ] && [ "$NL" != "$L" ] && LIVE=$((LIVE+1))
    [ "$AA" = "$N_ORD" ] && ADVOK=$((ADVOK+1))
    echo "$c,$k,$L,$NL,$([ "$NL" = "$TARGET" ] && echo 1 || echo 0),$([ "$NL" != 0 ] && echo 1 || echo 0),$AA" \
      >> "$OUT/elections.csv"
  done
  T1=$(date +%s); H1=$(height)

  rm -f "$STOP"; wait $RP 2>/dev/null
  [ -n "$HEAL" ] && kill $HEAL 2>/dev/null
  SEC=$((T1-T0)); BLK=$((H1-H0))
  RATE=$(awk -v b="$BLK" -v s="$SEC" 'BEGIN{printf "%.4f", (s>0? b/s : 0)}')
  echo "$c,$WINS,$N,$LIVE,$ADVOK,$H0,$H1,$BLK,$SEC,$RATE" >> "$OUT/summary.csv"
  printf "  %-18s target %2d/%-2d  live %2d/%-2d  advisors %2d/%-2d  blocks %4d in %4ds (%s /s)\n" \
    "$c" "$WINS" "$N" "$LIVE" "$N" "$ADVOK" "$N" "$BLK" "$SEC" "$RATE" | tee -a "$OUT/log.txt"
done

set_advice "[]"
tc_down
echo "POTENCY_DONE $OUT" | tee -a "$OUT/log.txt"
cat "$OUT/summary.csv" | tee -a "$OUT/log.txt"
