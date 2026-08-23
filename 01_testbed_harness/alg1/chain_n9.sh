#!/usr/bin/env bash
# Wait for the in-flight N=7 nsweep to finish (results.csv reaches header+4 rows),
# print its final results, then run N=9 to completion in this same process.
export PATH=/tmp/bin:/mnt/d/fabric-d2/fabric-samples/bin-linux/bin:/usr/local/bin:/usr/bin:/bin
sleep 8
D7=$(ls -dt /mnt/d/fabric-d2/results/nsweep_N7_* 2>/dev/null | head -1)
echo "CHAIN: watching $D7 for N=7 completion"
for i in $(seq 1 300); do            # up to ~50 min safety cap
  n=$(wc -l < "$D7/results.csv" 2>/dev/null || echo 0)
  if [ "${n:-0}" -ge 5 ]; then echo "CHAIN: N=7 results complete ($n lines)"; break; fi
  # bail early if the N=7 process is gone but results never completed
  if ! ps aux | grep -q "[n]sweep.sh 7"; then
    m=$(wc -l < "$D7/results.csv" 2>/dev/null || echo 0)
    if [ "${m:-0}" -lt 5 ]; then echo "CHAIN: WARNING N=7 process ended with only $m lines"; fi
    break
  fi
  sleep 10
done
echo "=== N=7 FINAL RESULTS ==="
cat "$D7/results.csv" 2>/dev/null
echo "--- N=7 summary ---"; cat "$D7/summary.txt" 2>/dev/null
echo ""
echo "=== CHAIN: launching N=9 ==="
bash /mnt/d/fabric-d2/alg1/nsweep.sh 9 2 10
echo "CHAIN: N=9 launch returned"
