#!/usr/bin/env bash
# NE26 Phase F: Caliper saturation against BORA-patched cluster.
# Same 3-phase pattern as Phase E (clean / attack-only / attack+BORA)
# but using Hyperledger Caliper to drive 600-900 tx/s instead of the
# CLI-bound concurrency sweep (~25 TPS ceiling).
set -e
RESULTS=/mnt/d/fabric-d2/results/ne26_phase_f_$(date +%Y%m%d-%H%M%S)
mkdir -p "$RESULTS"
WORKSPACE=/mnt/d/fabric-d2/caliper-workspace
CRYPTO=/mnt/d/fabric-d2/fabric-samples/test-network/organizations
ORDERERS=(orderer.example.com orderer2.example.com orderer3.example.com orderer4.example.com orderer5.example.com)

write_advice () {
  local payload="{\"blacklist\":$1,\"seq\":$2,\"fail_open\":$3}"
  for o in "${ORDERERS[@]}"; do
    docker exec "$o" sh -c "echo '$payload' > /tmp/bora-advice.json"
  done
}

run_caliper () {
  # $1 = seed, $2 = phase label, $3 = output dir
  docker rm -f caliper-d2 2>&1 | tail -1 || true
  docker run --rm \
    --name caliper-d2 \
    --network fabric_test \
    -v "$WORKSPACE:/hyperledger/caliper/workspace" \
    -v "$CRYPTO:/cryptoMount" \
    --add-host=host.docker.internal:host-gateway \
    -e CALIPER_BIND_SUT=fabric:fabric-gateway \
    -e CALIPER_BENCHCONFIG=benchmarks/saturation-refine.yaml \
    -e CALIPER_NETWORKCONFIG=networks/fabric-5node.yaml \
    -e CALIPER_FLOW_ONLY_TEST=true \
    -e CALIPER_REPORT_PATH=/hyperledger/caliper/workspace/report-$2-seed${1}.html \
    hyperledger/caliper:0.6.0 launch manager > "$3/caliper-$2-seed${1}.log" 2>&1
  cp "$WORKSPACE/report-$2-seed${1}.html" "$3/" 2>/dev/null || true
}

echo "============================================="
echo "NE26 Phase F — Caliper saturation, sidecar live"
echo "Results: $RESULTS"
echo "============================================="

# ---- Phase F1: clean ----
echo
echo "--- Phase F1: clean, B_t=[] ---"
write_advice "[]" 1000 "false"
mkdir -p "$RESULTS/phaseF1_clean"
for s in 1 2 3; do
  echo "  seed $s..."
  run_caliper "$s" "F1_clean" "$RESULTS/phaseF1_clean"
done

# ---- Phase F2: attack-only ----
echo
echo "--- Phase F2: attack on orderer3, B_t=[] ---"
mkdir -p "$RESULTS/phaseF2_attack_only"
docker run -d --name pumba-f2 -v /var/run/docker.sock:/var/run/docker.sock \
  gaiaadm/pumba:latest --interval 15m --log-level info \
  netem --tc-image gaiadocker/iproute2 --duration 12m \
  delay --time 200 orderer3.example.com 2>&1 | tail -1
sleep 5
write_advice "[]" 2000 "false"
for s in 1 2 3; do
  echo "  seed $s..."
  run_caliper "$s" "F2_attack" "$RESULTS/phaseF2_attack_only"
done
docker rm -f pumba-f2 2>&1 | tail -1 || true

# ---- Phase F3: attack + BORA active ----
echo
echo "--- Phase F3: attack + BORA B_t=[3] ---"
mkdir -p "$RESULTS/phaseF3_bora_active"
docker run -d --name pumba-f3 -v /var/run/docker.sock:/var/run/docker.sock \
  gaiaadm/pumba:latest --interval 15m --log-level info \
  netem --tc-image gaiadocker/iproute2 --duration 12m \
  delay --time 200 orderer3.example.com 2>&1 | tail -1
sleep 5
write_advice "[3]" 3000 "false"
for s in 1 2 3; do
  echo "  seed $s..."
  run_caliper "$s" "F3_bora" "$RESULTS/phaseF3_bora_active"
done
docker rm -f pumba-f3 2>&1 | tail -1 || true
write_advice "[]" 4000 "false"

# Parse Caliper HTML reports
echo
echo "--- Aggregate ---"
python3 - <<EOF
import os, re
from collections import defaultdict
import statistics as st
ROOT = "$RESULTS"
phases = [("phaseF1_clean", "F1 clean"),
          ("phaseF2_attack_only", "F2 attack-only"),
          ("phaseF3_bora_active", "F3 attack+BORA")]
results = defaultdict(lambda: defaultdict(list))
for d, lab in phases:
    full = os.path.join(ROOT, d)
    if not os.path.isdir(full):
        continue
    for fn in os.listdir(full):
        if fn.endswith(".html"):
            with open(os.path.join(full, fn), errors="ignore") as f:
                text = f.read()
            # Caliper HTML has table rows like:
            #   <td>send-rate</td><td>NNN</td>... <td>throughput</td><td>X.XX</td>
            # We pull "Throughput (TPS)" and "Max Latency" from each row.
            # Simpler regex over the simple-asset-transfer row labels.
            rows = re.findall(r'<tr.*?</tr>', text, re.S)
            for row in rows:
                m_rate = re.search(r'rate[^>]*>(\\d+)', row)
                m_tps = re.search(r'Throughput.*?>([\\d.]+)<', row)
                m_p99 = re.search(r'Max.*?>([\\d.]+)<', row)
                if m_rate and m_tps:
                    rate = int(m_rate.group(1))
                    tps = float(m_tps.group(1))
                    p99 = float(m_p99.group(1)) if m_p99 else float("nan")
                    results[lab][rate].append((tps, p99))
print(f"{'Phase':25}{'rate':>6}{'TPS':>14}{'p99(s)':>10}{'n':>4}")
print("-" * 60)
for lab in [l for _,l in phases]:
    for rate in sorted(results[lab]):
        rows = results[lab][rate]
        tps = [r[0] for r in rows]
        m = st.mean(tps); sd = st.stdev(tps) if len(tps)>1 else 0
        print(f"{lab:25}{rate:>6}  {m:>5.1f}±{sd:<4.1f}{'-':>10}{len(tps):>4}")
EOF

echo
echo "PHASE_F_OK"
echo "Results: $RESULTS"
