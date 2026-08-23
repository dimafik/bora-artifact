#!/bin/bash
# κ: Algorithm 1 simulation experiment
# Setup: orderer3 has 200ms burst-delay attack injected (matches ε)
# Phase A (ε baseline): system suffers from slow orderer3 in Raft consenter set
# Phase B (Algorithm 1): "blacklist" orderer3 by stopping it entirely
#   Raft cluster falls back to 4 orderers, quorum=3 still satisfied,
#   peer commits no longer wait for orderer3's slow ack
#   This is the SHADOW of paper's bounded-blacklist mechanism
set -e

RESULTS=/mnt/d/fabric-d2/results_alg1
rm -rf "$RESULTS"
mkdir -p "$RESULTS"

# Ensure we have a clean Fabric network with orderer3 healthy
echo "##################################################"
echo "############## κ-1: Bring up clean ###############"
echo "##################################################"
bash /mnt/d/fabric-d2/fresh-network.sh 2>&1 | tail -3

# Phase A: ε baseline — attack injected, no Algorithm 1
echo ""
echo "##################################################"
echo "##### κ-2 Phase A: ATTACK on orderer3 +200ms ####"
echo "##################################################"
docker run -d --name pumba-k-200 -v /var/run/docker.sock:/var/run/docker.sock \
  gaiaadm/pumba:latest --interval 10m --log-level info \
  netem --tc-image gaiadocker/iproute2 --duration 8m \
  delay --time 200 orderer3.example.com 2>&1 | tail -1
sleep 5

for s in 1 2 3; do
  bash /mnt/d/fabric-d2/concurrency-sweep-v2.sh "$s" 15 "$RESULTS/phaseA_attacked"
done

# Phase B: Algorithm 1 simulated — stop orderer3 entirely (= "blacklist")
echo ""
echo "##################################################"
echo "##### κ-3 Phase B: BLACKLIST orderer3 (Alg 1) ###"
echo "##################################################"
# Algorithm 1's bounded blacklist would effectively route around orderer3
# We simulate this by stopping orderer3 entirely; with 4/5 orderers alive,
# Raft quorum (3) still satisfied via orderer{1,2,4,5}
docker stop orderer3.example.com 2>&1 | tail -1
docker rm -f pumba-k-200 2>&1 | tail -1 || true
sleep 5

for s in 1 2 3; do
  bash /mnt/d/fabric-d2/concurrency-sweep-v2.sh "$s" 15 "$RESULTS/phaseB_blacklisted"
done

# Restore for cleanup
docker start orderer3.example.com 2>&1 | tail -1

echo ""
echo "##################################################"
echo "########### κ AGGREGATE COMPARISON ###############"
echo "##################################################"
python3 << PYEOF
import csv, os, statistics as st
phases = [("phaseA_attacked", "ε attack baseline"), ("phaseB_blacklisted", "Alg 1 simulated")]
print(f"{'phase':<22} {'C':>3} {'TPS_mean':>9} {'TPS_std':>8} {'p99_mean':>9}")
print("-" * 65)
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
        m = st.mean(tps); sd = st.stdev(tps) if len(tps)>1 else 0
        p = st.mean(p99) if p99 else 0
        print(f"{label:<22} {c:>3} {m:>9.2f} {sd:>8.2f} {p:>9.1f}")
PYEOF
