#!/usr/bin/env bash
# Gap 1: measure BORA detection latency.
# For each attack delay in {200,500,1000}ms, repeat 3 seeds:
#  T0 = time pumba injects netem rule on orderer3
#  T1 = time orderer1's sidecar logs first B_t containing [3]
#  detection_latency = T1 - T0
set -e
RESULTS=/mnt/d/fabric-d2/results/detection_latency_$(date +%Y%m%d-%H%M%S)
mkdir -p "$RESULTS"
ORDERERS=(orderer.example.com orderer2.example.com orderer3.example.com orderer4.example.com orderer5.example.com)
SIDECAR_BIN=/mnt/d/fabric-d2/results/bora-sidecar-v2.bin

deploy_v2 () {
  for i in "${!ORDERERS[@]}"; do
    o="${ORDERERS[$i]}"
    rid=$((i+1))
    docker cp "$SIDECAR_BIN" "$o:/tmp/bora-sidecar-v2" 2>/dev/null || true
    docker exec "$o" chmod +x /tmp/bora-sidecar-v2
    docker exec "$o" sh -c "pkill -f bora-sidecar 2>/dev/null; rm -f /var/run/raft-advisor.sock"
    sleep 0.3
    docker exec -d "$o" sh -c "/tmp/bora-sidecar-v2 -id $rid -log /tmp/bora-v2.log"
  done
  sleep 5
  for o in "${ORDERERS[@]}"; do
    docker exec "$o" sh -c 'test -S /var/run/raft-advisor.sock' && echo "  $o UDS up" || echo "  $o WARN no socket"
  done
}

measure_one () {
  local delay=$1; local seed=$2
  local out="$RESULTS/${delay}ms_seed${seed}.csv"
  echo "delay=$delay seed=$seed"
  # Truncate logs
  for o in "${ORDERERS[@]}"; do
    docker exec "$o" sh -c '> /tmp/bora-v2.log'
  done
  # Wait for sidecar window to fill
  sleep 20
  # Inject attack, capture T0 in ms epoch
  T0=$(date +%s%3N)
  docker run -d --name pumba-det-$delay-$seed -v /var/run/docker.sock:/var/run/docker.sock \
    gaiaadm/pumba:latest --interval 5m --log-level info \
    netem --tc-image gaiadocker/iproute2 --duration 2m \
    delay --time "$delay" orderer3.example.com > /dev/null 2>&1
  echo "  T0_ms=$T0"
  # Poll up to 60s for first Bt_change with id 3
  local T1=0
  for sec in $(seq 1 60); do
    sleep 1
    # Look at orderer1's sidecar log
    line=$(docker exec orderer.example.com sh -c 'grep "Bt_change" /tmp/bora-v2.log 2>/dev/null | grep "\[3\]\|3]" | head -1' 2>/dev/null)
    if [ -n "$line" ]; then
      T1=$(echo "$line" | sed -n 's/.*t=\([0-9]*\).*/\1/p')
      break
    fi
  done
  # Clean up pumba
  docker rm -f "pumba-det-$delay-$seed" > /dev/null 2>&1 || true
  # Wait for sidecar to clear Bt
  sleep 25
  # Write result
  if [ "$T1" -gt 0 ]; then
    LATENCY=$((T1 - T0))
    echo "  T1_ms=$T1  latency_ms=$LATENCY"
    echo "delay,seed,T0_ms,T1_ms,latency_ms" > "$out"
    echo "$delay,$seed,$T0,$T1,$LATENCY" >> "$out"
  else
    echo "  WARN no detection in 60s"
    echo "delay,seed,T0_ms,T1_ms,latency_ms" > "$out"
    echo "$delay,$seed,$T0,0,TIMEOUT" >> "$out"
  fi
}

echo "[1/2] Deploy sidecar v2..."
deploy_v2

echo "[2/2] Measurement campaign..."
for delay in 200 500 1000; do
  for seed in 1 2 3; do
    measure_one "$delay" "$seed"
  done
done

# Aggregate
echo
echo "--- Detection latency aggregate ---"
python3 - <<EOF
import csv, os, statistics
ROOT = "$RESULTS"
by_delay = {}
for fn in sorted(os.listdir(ROOT)):
    if not fn.endswith(".csv"):
        continue
    with open(os.path.join(ROOT, fn)) as f:
        rows = list(csv.DictReader(f))
        if rows:
            r = rows[0]
            d = int(r["delay"])
            lat = r["latency_ms"]
            if lat != "TIMEOUT":
                by_delay.setdefault(d, []).append(int(lat))
print(f"{'delay (ms)':>12}{'mean_lat':>12}{'std':>10}{'min':>8}{'max':>8}{'n':>4}")
print("-" * 60)
for d in sorted(by_delay):
    vs = by_delay[d]
    m = statistics.mean(vs); sd = statistics.stdev(vs) if len(vs)>1 else 0
    print(f"{d:>12}{m:>12.0f}{sd:>10.0f}{min(vs):>8}{max(vs):>8}{len(vs):>4}")
EOF

echo
echo "DETECTION_LATENCY_DONE"
echo "Results: $RESULTS"
