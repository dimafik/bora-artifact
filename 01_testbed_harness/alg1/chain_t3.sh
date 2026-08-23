#!/usr/bin/env bash
# Wait until task 2 (BORA forced elections) finishes, then run task 3 (throughput).
for i in $(seq 1 120); do
  f=$(ls -dt /mnt/d/fabric-d2/results/xhost_t2_* 2>/dev/null | head -1)
  if [ -n "$f" ] && grep -q "BORA_FORCED_TOTAL" "$f/summary.txt" 2>/dev/null; then
    echo "TASK2_DONE:"; grep "BORA_FORCED_TOTAL" "$f/summary.txt"
    break
  fi
  # bail if task 2 process gone
  ps aux | grep -q "[x]host_t2.sh" || { echo "task2 proc gone (i=$i)"; if [ -n "$f" ] && grep -q BORA_FORCED_TOTAL "$f/summary.txt" 2>/dev/null; then :; fi; }
  sleep 20
done
echo "=== launching task 3 ==="
bash /mnt/d/fabric-d2/alg1/xhost_t3.sh
echo "CHAIN_T3_DONE"
