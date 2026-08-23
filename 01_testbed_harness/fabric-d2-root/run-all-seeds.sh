#!/bin/bash
# Run concurrency sweep for 5 seeds, with isolated output dirs
set -e
for seed in 1 2 3 4 5; do
  export SEED=$seed
  export N_TX_PER_THREAD=20
  echo ""
  echo "##################################################"
  echo "############# SEED $seed #########################"
  echo "##################################################"
  bash /mnt/d/fabric-d2/concurrency-sweep.sh 2>&1 | grep -E "^C=|Concurrency"
done

echo ""
echo "############# AGGREGATE ACROSS SEEDS #############"
python3 << 'PYEOF'
import csv, os, statistics as st
runs = []
for s in [1,2,3,4,5]:
    f = f"/mnt/d/fabric-d2/results/seed{s}/conc_sweep/summary.csv"
    if not os.path.exists(f): continue
    with open(f) as fp:
        for row in csv.DictReader(fp):
            row['seed'] = s
            runs.append(row)

by_c = {}
for r in runs:
    c = r['concurrency']
    by_c.setdefault(c, []).append(r)

print(f"{'C':>3}  {'TPS_mean':>9}  {'TPS_std':>8}  {'p95_mean':>9}  {'p99_mean':>9}  {'lat_mean':>9}  {'n_seeds':>8}")
for c in sorted(by_c.keys(), key=int):
    rs = by_c[c]
    tps = [float(r['tps_total']) for r in rs]
    p95 = [float(r['p95']) for r in rs]
    p99 = [float(r['p99']) for r in rs]
    lat = [float(r['mean_latency_ms']) for r in rs]
    tps_mean = st.mean(tps); tps_std = st.stdev(tps) if len(tps)>1 else 0
    p95_mean = st.mean(p95); p99_mean = st.mean(p99); lat_mean = st.mean(lat)
    print(f"{c:>3}  {tps_mean:>9.2f}  {tps_std:>8.2f}  {p95_mean:>9.1f}  {p99_mean:>9.1f}  {lat_mean:>9.1f}  {len(rs):>8d}")
PYEOF
