#!/bin/bash
# δ: Caliper saturation refinement
# Each seed = fresh network + Caliper sweep at 600/700/800/900 tx/s
set -e

WORKSPACE=/mnt/d/fabric-d2/caliper-workspace
CRYPTO=/mnt/d/fabric-d2/fabric-samples/test-network/organizations
ARCHIVE=/mnt/d/fabric-d2/results/archive/5node_saturation_delta_2026-06-08
mkdir -p "$ARCHIVE"

run_caliper() {
  local seed=$1
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
    -e CALIPER_REPORT_PATH=/hyperledger/caliper/workspace/report-delta-seed${seed}.html \
    hyperledger/caliper:0.6.0 launch manager > "$WORKSPACE/caliper-delta-seed${seed}.log" 2>&1
}

for seed in 1 2 3; do
  echo ""
  echo "################################################"
  echo "############ δ SEED $seed ######################"
  echo "################################################"

  echo "[1/3] Fresh network bring-up..."
  bash /mnt/d/fabric-d2/fresh-network.sh 2>&1 | tail -3

  echo "[2/3] Caliper saturation sweep (600/700/800/900 × 30s)..."
  run_caliper "$seed"

  echo "[3/3] Archive seed $seed..."
  cp "$WORKSPACE/report-delta-seed${seed}.html" "$ARCHIVE/" 2>&1 | tail -1 || true
  cp "$WORKSPACE/caliper-delta-seed${seed}.log" "$ARCHIVE/" 2>&1 | tail -1 || true
done

echo ""
echo "==================== δ AGGREGATE ===================="
python3 << 'PYEOF'
import re, os, statistics as st
from pathlib import Path

ARCHIVE = Path("/mnt/d/fabric-d2/results/archive/5node_saturation_delta_2026-06-08")
ROUNDS = ["rate-600", "rate-700", "rate-800", "rate-900"]
ROW_RE = re.compile(
    r"<td>(rate-\d+)</td>\s*<td>([\d.-]+)</td>\s*<td>([\d.-]+)</td>\s*<td>([\d.-]+)</td>\s*<td>([\d.-]+|-)</td>\s*<td>([\d.-]+|-)</td>\s*<td>([\d.-]+|-)</td>\s*<td>([\d.-]+)</td>"
)
ps = {}
for s in [1, 2, 3]:
    f = ARCHIVE / f"report-delta-seed{s}.html"
    if not f.exists(): continue
    rows = ROW_RE.findall(f.read_text())
    seen = set(); ps[s] = {}
    for m in rows:
        if m[0] in seen: continue
        seen.add(m[0])
        ps[s][m[0]] = {"succ": int(m[1]), "fail": int(m[2]), "thr": float(m[7]),
                       "avg": None if m[6] == "-" else float(m[6])}

print(f"\n{'seed':>4}  {'round':>9}  {'succ':>7}  {'fail':>6}  {'thr':>6}  {'avg_lat':>8}  {'succ%':>6}")
for s in sorted(ps):
    for r in ROUNDS:
        if r not in ps[s]: continue
        d = ps[s][r]
        total = d["succ"] + d["fail"]
        pct = 100.0 * d["succ"] / total if total > 0 else 0
        lat = "-" if d["avg"] is None else f"{d['avg']:.3f}"
        print(f"{s:>4}  {r:>9}  {d['succ']:>7}  {d['fail']:>6}  {d['thr']:>6.1f}  {lat:>8}  {pct:>5.1f}%")

print(f"\n{'round':>9}  {'thr_mean':>9}  {'thr_std':>8}  {'succ_pct_mean':>14}  {'avg_lat_mean':>12}")
for r in ROUNDS:
    thrs = [ps[s][r]["thr"] for s in ps if r in ps[s]]
    pcts = [100.0 * ps[s][r]["succ"] / max(1, ps[s][r]["succ"] + ps[s][r]["fail"]) for s in ps if r in ps[s]]
    lats = [ps[s][r]["avg"] for s in ps if r in ps[s] and ps[s][r]["avg"] is not None]
    if not thrs: continue
    m = st.mean(thrs); sd = st.stdev(thrs) if len(thrs) > 1 else 0
    pm = st.mean(pcts) if pcts else 0
    lm = st.mean(lats) if lats else 0
    print(f"{r:>9}  {m:>9.2f}  {sd:>8.2f}  {pm:>13.1f}%  {lm:>12.3f}")
PYEOF
