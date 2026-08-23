#!/usr/bin/env bash
# Commit-latency tails under every delay track.
#
# The throughput sweep found nothing: 500 ms of base delay cost 28%, and
# autocorrelation on top of it moved committed blocks by -0.7% to -4.1% with no
# monotone relation to the autocorrelation itself, inside a 2.1% run-to-run
# band.  But throughput is a mean over three minutes, and a bursty delay does
# its damage to the tail -- a stall that stretches p99 need not move the mean at
# all.  So this measures the same tracks with per-transaction commit latency.
#
# Order is rotated between repeats for the same reason as in the throughput
# sweep: with a fixed order every condition sits at a fixed position while the
# ledger grows underneath it, and the single-pass throughput run produced one
# 12% outlier that turned out to be position, not condition.
#
# Usage:  potency_latency.sh [repeats] [scale] [seconds] [workers] [pace]
set -u

REPS="${1:-2}"
SCALE="${2:-m500}"
SECS="${3:-180}"
WORKERS="${4:-4}"
PACE="${5:-1.0}"
N_ORD=7
TICK=0.15

TRACKS=/d/fabric-d2/results/potency
OUT="$TRACKS/lat_${SCALE}_$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT/samples"

CONDS=(nodelay healthy_white pgd_rho_0.0 pgd_rho_0.3 pgd_rho_0.6 pgd_rho_0.8 attack_class_ar1)
NC=${#CONDS[@]}

ord_name(){ if [ "$1" = 1 ]; then echo orderer.example.com; else echo "orderer$1.example.com"; fi; }

tc_up(){
  for i in $(seq 1 $N_ORD); do
    docker rm -f "tcl$i" >/dev/null 2>&1
    docker run -d --name "tcl$i" --net "container:$(ord_name $i)" --cap-add NET_ADMIN \
      --entrypoint sh gaiadocker/iproute2 -c "sleep 36000" >/dev/null 2>&1
  done
  sleep 3
}
tc_clear(){ for i in $(seq 1 $N_ORD); do docker exec "tcl$i" tc qdisc del dev eth0 root >/dev/null 2>&1; done; }
tc_down(){ tc_clear; for i in $(seq 1 $N_ORD); do docker rm -f "tcl$i" >/dev/null 2>&1; done; }

replay(){
  local csv="$1"
  while [ -f "$STOP" ]; do
    while IFS=, read -r d1 d2 d3 d4 d5 d6 d7; do
      [ -f "$STOP" ] || break
      docker exec tcl1 tc qdisc replace dev eth0 root netem delay "${d1}ms" 2>/dev/null &
      docker exec tcl2 tc qdisc replace dev eth0 root netem delay "${d2}ms" 2>/dev/null &
      docker exec tcl3 tc qdisc replace dev eth0 root netem delay "${d3}ms" 2>/dev/null &
      docker exec tcl4 tc qdisc replace dev eth0 root netem delay "${d4}ms" 2>/dev/null &
      docker exec tcl5 tc qdisc replace dev eth0 root netem delay "${d5}ms" 2>/dev/null &
      docker exec tcl6 tc qdisc replace dev eth0 root netem delay "${d6}ms" 2>/dev/null &
      docker exec tcl7 tc qdisc replace dev eth0 root netem delay "${d7}ms" 2>/dev/null &
      wait
      sleep $TICK
    done < "$csv"
  done
}

echo "repeat,position,condition,n,fail,p50,p90,p95,p99,max,mean" > "$OUT/latency.csv"
echo "=== latency x$REPS: scale=$SCALE secs=$SECS workers=$WORKERS pace=$PACE ===" | tee "$OUT/log.txt"

tc_up
trap 'rm -f "$STOP" 2>/dev/null; tc_down; exit 130' INT TERM

for rep in $(seq 1 "$REPS"); do
  echo "---- repeat $rep ----" | tee -a "$OUT/log.txt"
  for pos in $(seq 0 $((NC - 1))); do
    idx=$(( (pos + rep - 1) % NC ))
    c=${CONDS[$idx]}

    STOP="/tmp/lat_stop_$$"
    RP=""
    if [ "$c" = nodelay ]; then
      tc_clear
    else
      CSV="$TRACKS/${SCALE}_${c}.csv"
      [ -f "$CSV" ] || { echo "missing $CSV" | tee -a "$OUT/log.txt"; continue; }
      touch "$STOP"; replay "$CSV" & RP=$!
      sleep 8
    fi

    SAMP="$OUT/samples/r${rep}_${c}.txt"
    bash /d/fabric-d2/alg1/latgen.sh "$SECS" "$WORKERS" "$PACE" 2>/dev/null \
      | grep -aE '^-?[0-9]+$' > "$SAMP"
    [ -n "$RP" ] && { rm -f "$STOP"; wait $RP 2>/dev/null; }

    STAT=$(awk '
      { if ($1 < 0) { f++ } else { v[n++] = $1 } }
      END {
        if (n == 0) { print "0 " f+0 " - - - - - -"; exit }
        asort(v)
        q = "";
        split("0.50 0.90 0.95 0.99", ps, " ")
        for (j = 1; j <= 4; j++) {
          k = int(ps[j] * n); if (k < 1) k = 1; if (k > n) k = n
          q = q v[k] " "
        }
        s = 0; for (j = 1; j <= n; j++) s += v[j]
        printf "%d %d %s%d %.1f", n, f+0, q, v[n], s / n
      }' "$SAMP")

    read -r N FAIL P50 P90 P95 P99 MAX MEAN <<< "$STAT"
    echo "$rep,$((pos+1)),$c,$N,$FAIL,$P50,$P90,$P95,$P99,$MAX,$MEAN" >> "$OUT/latency.csv"
    printf "  r%d p%d %-18s n=%-4s fail=%-3s p50=%-6s p95=%-6s p99=%-6s max=%s\n" \
      "$rep" "$((pos+1))" "$c" "$N" "$FAIL" "$P50" "$P95" "$P99" "$MAX" | tee -a "$OUT/log.txt"
  done
done

tc_down
echo "LATENCY_DONE $OUT" | tee -a "$OUT/log.txt"
