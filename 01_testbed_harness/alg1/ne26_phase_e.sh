#!/usr/bin/env bash
# NE26 Phase E (end-to-end sidecar-live): three sub-phases.
#  Phase E1: clean network, sidecar serves empty B_t (vanilla equivalent)
#  Phase E2: orderer3 +200ms attack, sidecar STILL serves empty B_t
#  Phase E3: orderer3 +200ms attack, sidecar serves B_t=[3]  <-- BORA active
set -e
RESULTS=/mnt/d/fabric-d2/results/ne26_phase_e_$(date +%Y%m%d-%H%M%S)
mkdir -p "$RESULTS"
ORDERERS=(orderer.example.com orderer2.example.com orderer3.example.com orderer4.example.com orderer5.example.com)

write_advice () {
  # $1 = blacklist JSON array, $2 = seq, $3 = fail_open bool
  local payload="{\"blacklist\":$1,\"seq\":$2,\"fail_open\":$3}"
  for o in "${ORDERERS[@]}"; do
    docker exec "$o" sh -c "echo '$payload' > /tmp/bora-advice.json"
  done
}

echo "============================================="
echo "NE26 Phase E — sidecar-live measurement"
echo "Results: $RESULTS"
echo "============================================="

# Make sure sidecars are running
for o in "${ORDERERS[@]}"; do
  if ! docker exec "$o" sh -c 'test -S /var/run/raft-advisor.sock'; then
    echo "ERROR: sidecar UDS missing on $o; aborting"
    exit 1
  fi
done

# ---- Phase E1: clean, B_t empty ----
echo
echo "--- Phase E1: clean (no attack), B_t=[] ---"
mkdir -p "$RESULTS/phaseE1_clean"
write_advice "[]" 100 "false"
for s in 1 2 3; do
  echo "  seed $s..."
  bash /mnt/d/fabric-d2/concurrency-sweep-v2.sh "$s" 15 "$RESULTS/phaseE1_clean" 2>&1 | tail -3
done

# ---- Phase E2: attack on orderer3, B_t STILL empty ----
echo
echo "--- Phase E2: attack (no mitigation), B_t=[] ---"
mkdir -p "$RESULTS/phaseE2_attack_only"
docker run -d --name pumba-e2 -v /var/run/docker.sock:/var/run/docker.sock \
  gaiaadm/pumba:latest --interval 10m --log-level info \
  netem --tc-image gaiadocker/iproute2 --duration 5m \
  delay --time 200 orderer3.example.com 2>&1 | tail -1
sleep 5
write_advice "[]" 200 "false"
for s in 1 2 3; do
  echo "  seed $s..."
  bash /mnt/d/fabric-d2/concurrency-sweep-v2.sh "$s" 15 "$RESULTS/phaseE2_attack_only" 2>&1 | tail -3
done
docker rm -f pumba-e2 2>&1 | tail -1 || true

# ---- Phase E3: attack on orderer3 + BORA mitigates, B_t=[3] ----
echo
echo "--- Phase E3: attack + BORA active, B_t=[3] ---"
mkdir -p "$RESULTS/phaseE3_bora_active"
docker run -d --name pumba-e3 -v /var/run/docker.sock:/var/run/docker.sock \
  gaiaadm/pumba:latest --interval 10m --log-level info \
  netem --tc-image gaiadocker/iproute2 --duration 5m \
  delay --time 200 orderer3.example.com 2>&1 | tail -1
sleep 5
write_advice "[3]" 300 "false"
for s in 1 2 3; do
  echo "  seed $s..."
  bash /mnt/d/fabric-d2/concurrency-sweep-v2.sh "$s" 15 "$RESULTS/phaseE3_bora_active" 2>&1 | tail -3
done
docker rm -f pumba-e3 2>&1 | tail -1 || true

# Recovery: clear B_t
write_advice "[]" 400 "false"

# Aggregate
echo
echo "--- Aggregate ---"
python3 - <<EOF
import os, statistics
from collections import defaultdict
ROOT = "$RESULTS"
phases = [("phaseE1_clean", "E1 clean / B_t=[]"),
          ("phaseE2_attack_only", "E2 attack / B_t=[]"),
          ("phaseE3_bora_active", "E3 attack / B_t=[3]")]
print(f"{'Phase':25}{'C':>4}{'TPS':>12}{'p99(ms)':>10}{'n':>4}")
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
                    c = int(fs[0]); tps=float(fs[4]); p99=float(fs[8])
                    by[c]["tps"].append(tps); by[c]["p99"].append(p99)
    for c in sorted(by):
        st = by[c]
        if st["tps"]:
            m = statistics.mean(st["tps"]); sd = statistics.stdev(st["tps"]) if len(st["tps"])>1 else 0
            p99 = statistics.mean(st["p99"])
            print(f"{lab:25}{c:>4}  {m:>5.2f}±{sd:<4.2f}{p99:>10.0f}{len(st['tps']):>4}")
EOF

echo
echo "PHASE_E_OK"
echo "Results: $RESULTS"
