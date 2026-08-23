#!/usr/bin/env bash
# Live moment-matched attack: replay per-node netem delays from delays.csv.
# Baseline rows: all white. Attack rows: o3 AR(1), others white (matched
# marginal). A persistent probe records the resulting RTT into rtt_feed.csv;
# best_mm.pt then scores it offline (mm_analyze.py). Records attack-onset T0.
set -u
R=/mnt/d/fabric-d2/results
ORD=(x orderer.example.com orderer2.example.com orderer3.example.com orderer4.example.com orderer5.example.com)
NBASE=$(grep -o '"n_baseline": [0-9]*' "$R/delays_meta.json" | grep -o '[0-9]*')
echo "n_baseline=$NBASE"
docker rm -f rtt-probe tc1 tc2 tc3 tc4 tc5 >/dev/null 2>&1; rm -f "$R/rtt_feed.csv" "$R/mm_t0.txt"
# persistent probe
docker run -d --name rtt-probe --network fabric_test -v /mnt/d/fabric-d2:/feed \
  -v /mnt/d/fabric-d2/alg1/rtt_probe.py:/rtt_probe.py -e FEED=/feed/results/rtt_feed.csv \
  python:3.11-slim python /rtt_probe.py >/dev/null 2>&1
# tc sidecars sharing each orderer netns
for i in 1 2 3 4 5; do
  docker run -d --name tc$i --net container:${ORD[$i]} --cap-add NET_ADMIN --entrypoint sh \
    gaiadocker/iproute2 -c "sleep 900" >/dev/null 2>&1
done
sleep 3
for i in 1 2 3 4 5; do docker exec tc$i tc qdisc replace dev eth0 root netem delay 8ms 2>/dev/null; done
echo "sidecars up; replaying $(wc -l < "$R/delays.csv") ticks..."
row=0
while IFS=, read -r d1 d2 d3 d4 d5; do
  row=$((row+1))
  [ "$row" = "$((NBASE+1))" ] && { date +%s.%N > "$R/mm_t0.txt"; echo "[$row] ATTACK ONSET (o3 -> AR(1))"; }
  docker exec tc1 tc qdisc replace dev eth0 root netem delay ${d1}ms 2>/dev/null &
  docker exec tc2 tc qdisc replace dev eth0 root netem delay ${d2}ms 2>/dev/null &
  docker exec tc3 tc qdisc replace dev eth0 root netem delay ${d3}ms 2>/dev/null &
  docker exec tc4 tc qdisc replace dev eth0 root netem delay ${d4}ms 2>/dev/null &
  docker exec tc5 tc qdisc replace dev eth0 root netem delay ${d5}ms 2>/dev/null &
  wait
  sleep 0.15
done < "$R/delays.csv"
for i in 1 2 3 4 5; do docker exec tc$i tc qdisc del dev eth0 root 2>/dev/null; done
docker rm -f rtt-probe tc1 tc2 tc3 tc4 tc5 >/dev/null 2>&1
echo "MM_LIVE_DONE feed=$(wc -l < "$R/rtt_feed.csv") rows"
