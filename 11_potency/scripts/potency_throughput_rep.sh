#!/usr/bin/env bash
# Repeated throughput measurement with rotated condition order.
#
# The single-pass run gave one number per condition and no way to tell a real
# difference from run-to-run variation: the spread was -12.3% to +2.3% with the
# sign flipping between neighbouring autocorrelations, which is what noise looks
# like, but with n=1 that cannot be shown.
#
# Order is rotated rather than fixed.  In the first pass every condition ran at
# a fixed position while the ledger grew monotonically underneath, so any drift
# with ledger size was indistinguishable from a condition effect -- and the one
# outlier, -12.3%, sat at position 3.  Rotating by one each repeat gives every
# condition a different position in every pass, which balances position without
# needing randomness the shell cannot supply reproducibly.
#
# Usage:  potency_throughput_rep.sh [repeats] [scale] [seconds] [workers] [pace]
set -u

REPS="${1:-4}"
SCALE="${2:-m500}"
SECS="${3:-180}"
WORKERS="${4:-4}"
PACE="${5:-1.0}"
N_ORD=7
TICK=0.15

TRACKS=/d/fabric-d2/results/potency
OUT="$TRACKS/tputrep_${SCALE}_$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT"

CONDS=(nodelay healthy_white pgd_rho_0.0 pgd_rho_0.3 pgd_rho_0.6 pgd_rho_0.8 attack_class_ar1)
NC=${#CONDS[@]}

ord_name(){ if [ "$1" = 1 ]; then echo orderer.example.com; else echo "orderer$1.example.com"; fi; }

tc_up(){
  for i in $(seq 1 $N_ORD); do
    docker rm -f "tcr$i" >/dev/null 2>&1
    docker run -d --name "tcr$i" --net "container:$(ord_name $i)" --cap-add NET_ADMIN \
      --entrypoint sh gaiadocker/iproute2 -c "sleep 36000" >/dev/null 2>&1
  done
  sleep 3
}
tc_clear(){ for i in $(seq 1 $N_ORD); do docker exec "tcr$i" tc qdisc del dev eth0 root >/dev/null 2>&1; done; }
tc_down(){ tc_clear; for i in $(seq 1 $N_ORD); do docker rm -f "tcr$i" >/dev/null 2>&1; done; }

replay(){
  local csv="$1"
  while [ -f "$STOP" ]; do
    while IFS=, read -r d1 d2 d3 d4 d5 d6 d7; do
      [ -f "$STOP" ] || break
      docker exec tcr1 tc qdisc replace dev eth0 root netem delay "${d1}ms" 2>/dev/null &
      docker exec tcr2 tc qdisc replace dev eth0 root netem delay "${d2}ms" 2>/dev/null &
      docker exec tcr3 tc qdisc replace dev eth0 root netem delay "${d3}ms" 2>/dev/null &
      docker exec tcr4 tc qdisc replace dev eth0 root netem delay "${d4}ms" 2>/dev/null &
      docker exec tcr5 tc qdisc replace dev eth0 root netem delay "${d5}ms" 2>/dev/null &
      docker exec tcr6 tc qdisc replace dev eth0 root netem delay "${d6}ms" 2>/dev/null &
      docker exec tcr7 tc qdisc replace dev eth0 root netem delay "${d7}ms" 2>/dev/null &
      wait
      sleep $TICK
    done < "$csv"
  done
}

echo "repeat,position,condition,seconds,h0,h1,blocks,blocks_per_s,tx_ok,tx_tried,tx_per_s" > "$OUT/tput.csv"
echo "=== throughput x$REPS: scale=$SCALE secs=$SECS workers=$WORKERS pace=$PACE ===" | tee "$OUT/log.txt"

tc_up
trap 'rm -f "$STOP" 2>/dev/null; tc_down; exit 130' INT TERM

for rep in $(seq 1 "$REPS"); do
  echo "---- repeat $rep ----" | tee -a "$OUT/log.txt"
  for pos in $(seq 0 $((NC - 1))); do
    idx=$(( (pos + rep - 1) % NC ))          # rotate start by the repeat number
    c=${CONDS[$idx]}

    STOP="/tmp/tputrep_stop_$$"
    RP=""
    if [ "$c" = nodelay ]; then
      tc_clear
    else
      CSV="$TRACKS/${SCALE}_${c}.csv"
      [ -f "$CSV" ] || { echo "missing $CSV" | tee -a "$OUT/log.txt"; continue; }
      touch "$STOP"; replay "$CSV" & RP=$!
      sleep 8
    fi

    RES=$(bash /d/fabric-d2/alg1/loadgen.sh "$SECS" "$WORKERS" "$PACE" 2>&1 | tail -1)
    [ -n "$RP" ] && { rm -f "$STOP"; wait $RP 2>/dev/null; }

    SEC=$(echo "$RES" | grep -ao 'seconds=[0-9]*'        | cut -d= -f2)
    HH=$(echo "$RES"  | grep -ao 'height [0-9]*->[0-9]*' | sed 's/height //')
    H0=${HH%%->*}; H1=${HH##*->}
    BLK=$(echo "$RES" | grep -ao 'blocks=[0-9-]*'        | cut -d= -f2)
    BPS=$(echo "$RES" | grep -ao 'blocks_per_s=[0-9.-]*' | cut -d= -f2)
    OK=$(echo "$RES"  | grep -ao 'tx_ok=[0-9]*'          | cut -d= -f2)
    TR=$(echo "$RES"  | grep -ao 'tx_tried=[0-9]*'       | cut -d= -f2)
    TPS=$(echo "$RES" | grep -ao 'tx_per_s=[0-9.]*'      | cut -d= -f2)

    if [ -z "${BLK:-}" ]; then
      echo "  r$rep p$((pos+1)) $c: LOADGEN_FAILED -- $RES" | tee -a "$OUT/log.txt"
      continue
    fi
    echo "$rep,$((pos+1)),$c,$SEC,$H0,$H1,$BLK,$BPS,$OK,$TR,$TPS" >> "$OUT/tput.csv"
    printf "  r%d p%d %-18s blocks %3s (%s /s)  tx %4s/%-4s\n" \
      "$rep" "$((pos+1))" "$c" "$BLK" "$BPS" "$OK" "$TR" | tee -a "$OUT/log.txt"
  done
done

tc_down
echo "TPUTREP_DONE $OUT" | tee -a "$OUT/log.txt"
