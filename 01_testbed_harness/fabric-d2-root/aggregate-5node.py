import csv, os, statistics as st

runs = []
for s in [1, 2, 3, 4, 5]:
    f = f"/mnt/d/fabric-d2/results_5node/seed{s}/conc_sweep/summary.csv"
    if not os.path.exists(f):
        continue
    with open(f) as fp:
        for row in csv.DictReader(fp):
            row["seed"] = s
            runs.append(row)

by_c = {}
for r in runs:
    c = r["concurrency"]
    by_c.setdefault(c, []).append(r)

print(f"{'C':>3}  {'TPS_mean':>9}  {'TPS_std':>8}  {'lat_mean':>9}  {'p95_mean':>9}  {'p99_mean':>9}  {'n':>3}")
print("-" * 65)
for c in sorted(by_c.keys(), key=int):
    rs = by_c[c]
    tps = [float(r["tps_total"]) for r in rs if r.get("tps_total") and r["tps_total"].strip()]
    lat = [float(r["mean_latency_ms"]) for r in rs if r.get("mean_latency_ms") and r["mean_latency_ms"].strip()]
    p95 = [float(r["p95"]) for r in rs if r.get("p95") and r["p95"].strip()]
    p99 = [float(r["p99"]) for r in rs if r.get("p99") and r["p99"].strip()]
    if not tps:
        continue
    tps_m = st.mean(tps); tps_s = st.stdev(tps) if len(tps) > 1 else 0
    lat_m = st.mean(lat) if lat else 0
    p95_m = st.mean(p95) if p95 else 0
    p99_m = st.mean(p99) if p99 else 0
    print(f"{c:>3}  {tps_m:>9.2f}  {tps_s:>8.2f}  {lat_m:>9.1f}  {p95_m:>9.1f}  {p99_m:>9.1f}  {len(rs):>3d}")
