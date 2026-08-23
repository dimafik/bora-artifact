#!/usr/bin/env bash
# NE26 measurement: BORA-patched orderers, fail-open mode (no sidecar).
# Phase A_v3: clean network. Phase B_v3: orderer3 +200ms attack.
# Compare to existing vanilla baseline in master-kappa-iota-mu.log.
set -e
RESULTS=/mnt/d/fabric-d2/results/ne26_v3_$(date +%Y%m%d-%H%M%S)
mkdir -p "$RESULTS"

echo "=================================================="
echo "NE26 measurement: BORA-patched orderers v3.1.4"
echo "Output dir: $RESULTS"
echo "=================================================="

echo
echo "--- Phase A_v3: clean network (no attack) ---"
mkdir -p "$RESULTS/phaseA_clean"
for s in 1 2 3; do
  echo "  seed $s..."
  bash /mnt/d/fabric-d2/concurrency-sweep-v2.sh "$s" 15 "$RESULTS/phaseA_clean" 2>&1 | tail -3
done

echo
echo "--- Phase B_v3: orderer3 +200ms attack ---"
mkdir -p "$RESULTS/phaseB_attack"
docker run -d --name pumba-ne26 -v /var/run/docker.sock:/var/run/docker.sock \
  gaiaadm/pumba:latest --interval 10m --log-level info \
  netem --tc-image gaiadocker/iproute2 --duration 5m \
  delay --time 200 orderer3.example.com 2>&1 | tail -1
sleep 5
for s in 1 2 3; do
  echo "  seed $s under attack..."
  bash /mnt/d/fabric-d2/concurrency-sweep-v2.sh "$s" 15 "$RESULTS/phaseB_attack" 2>&1 | tail -3
done
docker rm -f pumba-ne26 2>&1 | tail -1 || true

echo
echo "--- Aggregate summary ---"
python3 - <<EOF
import os, glob, statistics
from collections import defaultdict
ROOT = "$RESULTS"
phases = [("phaseA_clean", "Phase A_v3 (BORA-patched, no attack)"),
          ("phaseB_attack", "Phase B_v3 (BORA-patched, orderer3 +200ms)")]
print(f"{'Phase':40} {'C':>3} {'TPS':>8} {'p99(ms)':>10} {'fail%':>7} {'n_seed':>8}")
print("-" * 80)
for phdir, label in phases:
    by_c = defaultdict(lambda: {"tps": [], "p99": [], "fail": []})
    for seed in (1,2,3):
        csv = os.path.join(ROOT, phdir, f"seed{seed}/conc_sweep/summary.csv")
        if not os.path.exists(csv):
            continue
        with open(csv) as f:
            lines = f.read().strip().split("\n")
            for line in lines[1:]:
                fields = line.split(",")
                if len(fields) >= 5:
                    c = int(fields[0]); tps = float(fields[1])
                    p99 = float(fields[3]); fp = float(fields[4])
                    by_c[c]["tps"].append(tps)
                    by_c[c]["p99"].append(p99)
                    by_c[c]["fail"].append(fp)
    for c in sorted(by_c):
        st = by_c[c]
        if st["tps"]:
            print(f"{label:40} {c:>3} {statistics.mean(st['tps']):>8.2f} {statistics.mean(st['p99']):>10.1f} {statistics.mean(st['fail']):>7.1f} {len(st['tps']):>8}")
EOF
echo
echo "NE26_MEASURE_OK"
echo "Results: $RESULTS"
