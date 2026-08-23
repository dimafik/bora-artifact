#!/usr/bin/env bash
# Throughput half of the potency question: under each delay track, how much does
# the ordering service actually commit?
#
# Same tracks and same injection as the election campaign, but the cluster is
# driven with a fixed offered load instead of forced elections.  A "nodelay"
# control runs first: without it a low figure under every track could mean the
# 500 ms base delay costs everything and the autocorrelation costs nothing, and
# there would be no way to tell that from the tracks alone.
#
# Committed blocks come from the ledger, not from the client.  A client-side
# timeout was once read as a consensus failure in this project and produced a
# retracted throughput claim; the ledger cannot lie about what was committed.
#
# Usage:  potency_throughput.sh <scale> [seconds] [workers]
set -u

SCALE="${1:-m500}"
SECS="${2:-180}"
WORKERS="${3:-4}"
# Paced, so the offered load is identical in every condition.  Unthrottled, a
# slower condition completes fewer attempts per second, so the input to the
# comparison would vary with the thing being compared.
PACE="${4:-1.0}"
N_ORD=7
TICK=0.15

TRACKS=/d/fabric-d2/results/potency
OUT="$TRACKS/tput_${SCALE}_$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT"

CONDS="nodelay healthy_white pgd_rho_0.0 pgd_rho_0.3 pgd_rho_0.6 pgd_rho_0.8 attack_class_ar1"

ord_name(){ if [ "$1" = 1 ]; then echo orderer.example.com; else echo "orderer$1.example.com"; fi; }

tc_up(){
  for i in $(seq 1 $N_ORD); do
    docker rm -f "tct$i" >/dev/null 2>&1
    docker run -d --name "tct$i" --net "container:$(ord_name $i)" --cap-add NET_ADMIN \
      --entrypoint sh gaiadocker/iproute2 -c "sleep 36000" >/dev/null 2>&1
  done
  sleep 3
}
tc_clear(){ for i in $(seq 1 $N_ORD); do docker exec "tct$i" tc qdisc del dev eth0 root >/dev/null 2>&1; done; }
tc_down(){ tc_clear; for i in $(seq 1 $N_ORD); do docker rm -f "tct$i" >/dev/null 2>&1; done; }

replay(){
  local csv="$1"
  while [ -f "$STOP" ]; do
    while IFS=, read -r d1 d2 d3 d4 d5 d6 d7; do
      [ -f "$STOP" ] || break
      docker exec tct1 tc qdisc replace dev eth0 root netem delay "${d1}ms" 2>/dev/null &
      docker exec tct2 tc qdisc replace dev eth0 root netem delay "${d2}ms" 2>/dev/null &
      docker exec tct3 tc qdisc replace dev eth0 root netem delay "${d3}ms" 2>/dev/null &
      docker exec tct4 tc qdisc replace dev eth0 root netem delay "${d4}ms" 2>/dev/null &
      docker exec tct5 tc qdisc replace dev eth0 root netem delay "${d5}ms" 2>/dev/null &
      docker exec tct6 tc qdisc replace dev eth0 root netem delay "${d6}ms" 2>/dev/null &
      docker exec tct7 tc qdisc replace dev eth0 root netem delay "${d7}ms" 2>/dev/null &
      wait
      sleep $TICK
    done < "$csv"
  done
}

echo "condition,seconds,h0,h1,blocks,blocks_per_s,tx_ok,tx_tried,tx_per_s" > "$OUT/tput.csv"
echo "=== throughput: scale=$SCALE secs=$SECS workers=$WORKERS ===" | tee "$OUT/log.txt"

tc_up
trap 'rm -f "$STOP" 2>/dev/null; tc_down; exit 130' INT TERM

for c in $CONDS; do
  STOP="/tmp/tput_stop_$$"
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

  # parse "workers=4 seconds=180 height 12->99 blocks=87 blocks_per_s=0.4833 tx_ok=.. tx_tried=.. tx_per_s=.."
  SEC=$(echo "$RES"  | grep -ao 'seconds=[0-9]*'        | cut -d= -f2)
  HH=$(echo "$RES"   | grep -ao 'height [0-9]*->[0-9]*' | sed 's/height //')
  H0=${HH%%->*}; H1=${HH##*->}
  BLK=$(echo "$RES"  | grep -ao 'blocks=[0-9]*'         | cut -d= -f2)
  BPS=$(echo "$RES"  | grep -ao 'blocks_per_s=[0-9.]*'  | cut -d= -f2)
  OK=$(echo "$RES"   | grep -ao 'tx_ok=[0-9]*'          | cut -d= -f2)
  TR=$(echo "$RES"   | grep -ao 'tx_tried=[0-9]*'       | cut -d= -f2)
  TPS=$(echo "$RES"  | grep -ao 'tx_per_s=[0-9.]*'      | cut -d= -f2)

  if [ -z "${BLK:-}" ]; then
    echo "  $c: LOADGEN_FAILED -- $RES" | tee -a "$OUT/log.txt"
    echo "$c,,,,,,,," >> "$OUT/tput.csv"
    continue
  fi
  echo "$c,$SEC,$H0,$H1,$BLK,$BPS,$OK,$TR,$TPS" >> "$OUT/tput.csv"
  printf "  %-18s blocks %4s (%s /s)  tx %5s/%-5s (%s /s)\n" \
    "$c" "$BLK" "$BPS" "$OK" "$TR" "$TPS" | tee -a "$OUT/log.txt"
done

tc_down
echo "TPUT_DONE $OUT" | tee -a "$OUT/log.txt"
cat "$OUT/tput.csv" | tee -a "$OUT/log.txt"
