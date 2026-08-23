#!/bin/bash
# Measure 5-orderer Raft TPS under burst-delay attack on orderer3.
# Compares: clean baseline vs orderer3-delayed-200ms vs orderer3-delayed-500ms
set -e

RESULTS=/mnt/d/fabric-d2/results_attack
rm -rf "$RESULTS"
mkdir -p "$RESULTS"

# --- BASELINE: clean network ---
echo ""
echo "##################################################"
echo "########### PHASE 1: CLEAN BASELINE ##############"
echo "##################################################"
for s in 1 2 3; do
  bash /mnt/d/fabric-d2/concurrency-sweep-v2.sh "$s" 15 "$RESULTS/clean"
done

# --- ATTACK 200ms: pumba injects 200ms delay on orderer3 ---
echo ""
echo "##################################################"
echo "######## PHASE 2: ATTACK orderer3 +200ms #########"
echo "##################################################"
echo "Starting pumba delay (200ms) on orderer3.example.com for 4 minutes..."
docker run -d --name pumba-attack-200 -v /var/run/docker.sock:/var/run/docker.sock \
  gaiaadm/pumba:latest --interval 10m --log-level info \
  netem --tc-image gaiadocker/iproute2 --duration 4m \
  delay --time 200 orderer3.example.com 2>&1 | tail -1

sleep 5
docker logs pumba-attack-200 2>&1 | tail -3

for s in 1 2 3; do
  bash /mnt/d/fabric-d2/concurrency-sweep-v2.sh "$s" 15 "$RESULTS/attack_200ms"
done

docker rm -f pumba-attack-200 2>&1 | tail -1 || true
sleep 5  # allow tc rules to clear

# --- ATTACK 500ms: heavier delay ---
echo ""
echo "##################################################"
echo "######## PHASE 3: ATTACK orderer3 +500ms #########"
echo "##################################################"
docker run -d --name pumba-attack-500 -v /var/run/docker.sock:/var/run/docker.sock \
  gaiaadm/pumba:latest --interval 10m --log-level info \
  netem --tc-image gaiadocker/iproute2 --duration 4m \
  delay --time 500 orderer3.example.com 2>&1 | tail -1

sleep 5
for s in 1 2 3; do
  bash /mnt/d/fabric-d2/concurrency-sweep-v2.sh "$s" 15 "$RESULTS/attack_500ms"
done

docker rm -f pumba-attack-500 2>&1 | tail -1 || true

echo ""
echo "##################################################"
echo "############ AGGREGATE COMPARISON ################"
echo "##################################################"
python3 << PYEOF
import csv, os, statistics as st
phases = [("clean", "Clean baseline"), ("attack_200ms", "orderer3 +200ms"), ("attack_500ms", "orderer3 +500ms")]
print(f"{'phase':<20} {'C':>3} {'TPS_mean':>9} {'TPS_std':>8} {'p99_mean':>9}")
print("-" * 60)
for phase, label in phases:
    by_c = {}
    for s in [1,2,3]:
        f = f"$RESULTS/{phase}/seed{s}/conc_sweep/summary.csv"
        if not os.path.exists(f): continue
        with open(f) as fp:
            for row in csv.DictReader(fp):
                if row.get("tps_total") and row["tps_total"].strip():
                    by_c.setdefault(row["concurrency"], []).append(row)
    for c in sorted(by_c, key=int):
        tps = [float(r["tps_total"]) for r in by_c[c]]
        p99 = [float(r["p99"]) for r in by_c[c] if r.get("p99") and r["p99"].strip()]
        m = st.mean(tps); s = st.stdev(tps) if len(tps)>1 else 0
        p = st.mean(p99) if p99 else 0
        print(f"{label:<20} {c:>3} {m:>9.2f} {s:>8.2f} {p:>9.1f}")
PYEOF
