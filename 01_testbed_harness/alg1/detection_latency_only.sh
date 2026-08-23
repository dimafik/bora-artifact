#!/usr/bin/env bash
# Measurement-only variant: assumes sidecar v2 is already running on all 5 orderers.
set -e
RESULTS=/mnt/d/fabric-d2/results/detection_latency_$(date +%Y%m%d-%H%M%S)
mkdir -p "$RESULTS"
ORDERERS=(orderer.example.com orderer2.example.com orderer3.example.com orderer4.example.com orderer5.example.com)

measure_one () {
  local delay=$1; local seed=$2
  local out="$RESULTS/${delay}ms_seed${seed}.csv"
  echo "delay=${delay}ms seed=$seed"
  # Truncate logs everywhere
  for o in "${ORDERERS[@]}"; do
    docker exec "$o" sh -c '> /tmp/bora-v2.log' 2>/dev/null || true
  done
  # Wait for window to fill (16s) + margin
  sleep 22
  # Inject attack, capture T0 in ms epoch
  T0=$(date +%s%3N)
  docker run -d --name "pumba-det-${delay}-${seed}" -v /var/run/docker.sock:/var/run/docker.sock \
    gaiaadm/pumba:latest --interval 5m --log-level info \
    netem --tc-image gaiadocker/iproute2 --duration 2m \
    delay --time "$delay" orderer3.example.com > /dev/null 2>&1
  echo "  T0_ms=$T0"
  # Poll up to 60s for first Bt with id 3 in any sidecar
  local T1=0
  for sec in $(seq 1 60); do
    sleep 1
    # Look at orderer1's sidecar log: find Bt_change with "3]" or "[3"
    line=$(docker exec orderer.example.com cat /tmp/bora-v2.log 2>/dev/null | grep "Bt_change" | grep -E "\[.*3.*\]" | head -1)
    if [ -n "$line" ]; then
      T1=$(echo "$line" | sed -n 's/.*t=\([0-9]*\).*/\1/p')
      break
    fi
  done
  # Clean up pumba
  docker rm -f "pumba-det-${delay}-${seed}" > /dev/null 2>&1 || true
  # Wait for B_t to clear
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
