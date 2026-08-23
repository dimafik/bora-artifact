#!/bin/bash
echo "=== MANIFEST.json (head) ==="
head -50 /mnt/d/fabric-d2/results/archive/MANIFEST.json

echo ""
echo "=== Archive metadata check ==="
for d in /mnt/d/fabric-d2/results/archive/*/; do
  n=$(basename "$d")
  if [ -f "$d/metadata.json" ]; then
    echo "$n  ->  metadata.json OK"
  else
    echo "$n  ->  MISSING"
  fi
done

echo ""
echo "=== Total transactions from MANIFEST ==="
python3 -c "import json; m = json.load(open('/mnt/d/fabric-d2/results/archive/MANIFEST.json')); print(f'Total tx: {m[\"campaign_totals\"][\"total_executed_transactions\"]:,}'); print(f'Phases: {len(m[\"experimental_phases_summary\"])}')"
