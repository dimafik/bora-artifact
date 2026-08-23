#!/usr/bin/env bash
# NE26 Phase G: stronger attack (500ms delay on orderer3) to surface
# the BORA effect that 200ms was too weak to elicit.
# Three sub-phases:
#  G1: clean (control)
#  G2: 500ms attack, B_t=[]
#  G3: 500ms attack, B_t=[3]
set -e
RESULTS=/mnt/d/fabric-d2/results/ne26_phase_g_$(date +%Y%m%d-%H%M%S)
mkdir -p "$RESULTS"
ORDERERS=(orderer.example.com orderer2.example.com orderer3.example.com orderer4.example.com orderer5.example.com)

write_advice () {
  local payload="{\"blacklist\":$1,\"seq\":$2,\"fail_open\":$3}"
  for o in "${ORDERERS[@]}"; do
    docker exec "$o" sh -c "echo '$payload' > /tmp/bora-advice.json"
  done
}

echo "==========================================="
echo "NE26 Phase G — 500ms attack on orderer3"
echo "Results: $RESULTS"
echo "==========================================="

# G1: clean
echo
echo "--- G1: clean, B_t=[] ---"
mkdir -p "$RESULTS/phaseG1_clean"
write_advice "[]" 10000 "false"
for s in 1 2 3; do
  echo "  seed $s..."
  bash /mnt/d/fabric-d2/concurrency-sweep-v2.sh "$s" 15 "$RESULTS/phaseG1_clean" 2>&1 | tail -3
done

# G2: 500ms attack no BORA
echo
echo "--- G2: 500ms attack, B_t=[] ---"
mkdir -p "$RESULTS/phaseG2_attack_only"
docker run -d --name pumba-g2 -v /var/run/docker.sock:/var/run/docker.sock \
  gaiaadm/pumba:latest --interval 10m --log-level info \
  netem --tc-image gaiadocker/iproute2 --duration 6m \
  delay --time 500 orderer3.example.com 2>&1 | tail -1
sleep 5
write_advice "[]" 20000 "false"
for s in 1 2 3; do
  echo "  seed $s..."
  bash /mnt/d/fabric-d2/concurrency-sweep-v2.sh "$s" 15 "$RESULTS/phaseG2_attack_only" 2>&1 | tail -3
done
docker rm -f pumba-g2 2>&1 | tail -1 || true

# G3: 500ms attack BORA active
echo
echo "--- G3: 500ms attack, B_t=[3] ---"
mkdir -p "$RESULTS/phaseG3_bora_active"
docker run -d --name pumba-g3 -v /var/run/docker.sock:/var/run/docker.sock \
  gaiaadm/pumba:latest --interval 10m --log-level info \
  netem --tc-image gaiadocker/iproute2 --duration 6m \
  delay --time 500 orderer3.example.com 2>&1 | tail -1
sleep 5
write_advice "[3]" 30000 "false"
for s in 1 2 3; do
  echo "  seed $s..."
  bash /mnt/d/fabric-d2/concurrency-sweep-v2.sh "$s" 15 "$RESULTS/phaseG3_bora_active" 2>&1 | tail -3
done
docker rm -f pumba-g3 2>&1 | tail -1 || true
write_advice "[]" 40000 "false"

# Aggregate
echo
echo "--- Aggregate ---"
python3 - <<EOF
import os
from collections import defaultdict
import statistics as st
ROOT = "$RESULTS"
phases = [("phaseG1_clean", "G1 clean"),
          ("phaseG2_attack_only", "G2 attack-only 500ms"),
          ("phaseG3_bora_active", "G3 attack+BORA 500ms")]
print(f"{'Phase':28}{'C':>4}{'TPS':>14}{'p99(ms)':>10}{'n':>4}")
print("-" * 60)
for d, lab in phases:
    by = defaultdict(lambda: {"tps": [], "p99": []})
    for s in (1,2,3):
        f = os.path.join(ROOT, d, f"seed{s}/conc_sweep/summary.csv")
        if not os.path.exists(f):
            continue
        with open(f) as fh:
            for line in fh.read().strip().split("\n")[1:]:
                fs = line.split(",")
                if len(fs) >= 9:
                    c=int(fs[0]); tps=float(fs[4]); p99=float(fs[8])
                    by[c]["tps"].append(tps); by[c]["p99"].append(p99)
    for c in sorted(by):
        s_ = by[c]
        if s_["tps"]:
            m = st.mean(s_["tps"]); sd = st.stdev(s_["tps"]) if len(s_["tps"])>1 else 0
            p99 = st.mean(s_["p99"])
            print(f"{lab:28}{c:>4}  {m:>5.2f}±{sd:<4.2f}{p99:>10.0f}{len(s_['tps']):>4}")
EOF
echo
echo "PHASE_G_OK"
echo "Results: $RESULTS"
