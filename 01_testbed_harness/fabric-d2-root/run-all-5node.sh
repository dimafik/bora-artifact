#!/bin/bash
# Run 5-seed concurrency sweep on 5-orderer Raft cluster
set -e
ROOT=/mnt/d/fabric-d2/results_5node
rm -rf "$ROOT"
mkdir -p "$ROOT"

for s in 1 2 3 4 5; do
  echo "==================== SEED $s ===================="
  bash /mnt/d/fabric-d2/concurrency-sweep-v2.sh "$s" 20 "$ROOT"
done

echo ""
echo "==================== AGGREGATE ===================="
python3 /mnt/d/fabric-d2/aggregate-5node.py
