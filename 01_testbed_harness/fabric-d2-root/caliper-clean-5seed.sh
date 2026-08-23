#!/bin/bash
# Clean 5-seed Caliper sweep: fresh network bring-up between each seed.
set -e

WORKSPACE=/mnt/d/fabric-d2/caliper-workspace
CRYPTO=/mnt/d/fabric-d2/fabric-samples/test-network/organizations
ARCHIVE=/mnt/d/fabric-d2/results/archive/5node_caliper_clean_2026-06-07
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
    -e CALIPER_BENCHCONFIG=benchmarks/createasset-clean.yaml \
    -e CALIPER_NETWORKCONFIG=networks/fabric-5node.yaml \
    -e CALIPER_FLOW_ONLY_TEST=true \
    -e CALIPER_REPORT_PATH=/hyperledger/caliper/workspace/report-clean-seed${seed}.html \
    hyperledger/caliper:0.6.0 launch manager > "$WORKSPACE/caliper-clean-seed${seed}.log" 2>&1
}

for seed in 1 2 3 4 5; do
  echo ""
  echo "################################################"
  echo "############ SEED $seed ########################"
  echo "################################################"

  echo "[1/3] Fresh network bring-up..."
  bash /mnt/d/fabric-d2/fresh-network.sh 2>&1 | tail -3
  sleep 5

  echo "[2/3] Caliper sweep (rate-100/300/500 x 30s)..."
  run_caliper "$seed"

  echo "[3/3] Archive seed $seed..."
  cp "$WORKSPACE/report-clean-seed${seed}.html" "$ARCHIVE/" 2>&1 | tail -1 || true
  cp "$WORKSPACE/caliper-clean-seed${seed}.log" "$ARCHIVE/" 2>&1 | tail -1 || true

  # Quick summary
  grep -E "Finished round|throughput|Avg Latency|<td>rate-" "$WORKSPACE/report-clean-seed${seed}.html" | tail -10 || true
done

echo ""
echo "==================== AGGREGATE ===================="
python3 << 'PYEOF'
import re, os, statistics as st
from pathlib import Path

ARCHIVE = Path("/mnt/d/fabric-d2/results/archive/5node_caliper_clean_2026-06-07")
ROUNDS = ["rate-100", "rate-300", "rate-500"]
ROW_RE = re.compile(
    r"<td>(rate-\d+)</td>\s*<td>([\d.-]+)</td>\s*<td>([\d.-]+)</td>\s*<td>([\d.-]+)</td>\s*<td>([\d.-]+|-)</td>\s*<td>([\d.-]+|-)</td>\s*<td>([\d.-]+|-)</td>\s*<td>([\d.-]+)</td>"
)

per_seed = {}
for s in range(1, 6):
    f = ARCHIVE / f"report-clean-seed{s}.html"
    if not f.exists():
        continue
    text = f.read_text()
    rows = ROW_RE.findall(text)
    seen = set()
    per_seed[s] = {}
    for m in rows:
        name = m[0]
        if name in seen:
            continue
        seen.add(name)
        per_seed[s][name] = {
            "succ": int(m[1]),
            "fail": int(m[2]),
            "send": float(m[3]),
            "thr": float(m[7]),
            "avg_lat": None if m[6] == "-" else float(m[6]),
        }

print(f"\n{'seed':>4}  {'round':>9}  {'succ':>7}  {'fail':>5}  {'thr':>6}  {'avg_lat':>7}")
for s in sorted(per_seed):
    for r in ROUNDS:
        if r not in per_seed[s]:
            print(f"{s:>4}  {r:>9}  (missing)")
            continue
        d = per_seed[s][r]
        lat = "-" if d["avg_lat"] is None else f"{d['avg_lat']:.3f}"
        print(f"{s:>4}  {r:>9}  {d['succ']:>7}  {d['fail']:>5}  {d['thr']:>6.1f}  {lat:>7}")

print(f"\n{'round':>9}  {'thr_mean':>9}  {'thr_std':>8}  {'lat_mean':>9}  {'n':>3}")
for r in ROUNDS:
    thr = [per_seed[s][r]["thr"] for s in per_seed if r in per_seed[s] and per_seed[s][r]["succ"] > 0]
    lat = [per_seed[s][r]["avg_lat"] for s in per_seed if r in per_seed[s] and per_seed[s][r]["avg_lat"] is not None]
    if not thr:
        continue
    m = st.mean(thr); sd = st.stdev(thr) if len(thr) > 1 else 0
    lm = st.mean(lat) if lat else 0
    print(f"{r:>9}  {m:>9.2f}  {sd:>8.2f}  {lm:>9.3f}  {len(thr):>3d}")
PYEOF
