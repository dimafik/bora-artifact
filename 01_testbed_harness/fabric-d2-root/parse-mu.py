import csv, os, statistics as st

print(f"{'C':>3} {'TPS_mean':>9} {'TPS_std':>8} {'p99_mean':>9} {'ok_total':>9} {'fail_total':>10}")
print("-" * 60)
by_c = {}
for s in [1, 2, 3]:
    f = f"/mnt/d/fabric-d2/results_mu/seed{s}/conc_sweep/summary.csv"
    if not os.path.exists(f):
        continue
    with open(f) as fp:
        for row in csv.DictReader(fp):
            if row.get("tps_total") and row["tps_total"].strip():
                by_c.setdefault(row["concurrency"], []).append(row)

for c in sorted(by_c, key=int):
    tps = [float(r["tps_total"]) for r in by_c[c]]
    p99 = [float(r["p99"]) for r in by_c[c] if r.get("p99") and r["p99"].strip()]
    ok = sum(int(r["ok"]) for r in by_c[c])
    fail = sum(int(r["fail"]) for r in by_c[c])
    m = st.mean(tps); sd = st.stdev(tps) if len(tps) > 1 else 0
    p = st.mean(p99) if p99 else 0
    print(f"{c:>3} {m:>9.2f} {sd:>8.2f} {p:>9.1f} {ok:>9d} {fail:>10d}")
