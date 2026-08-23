"""Parse Caliper HTML reports for D2-β2 5-seed sweep results."""
import re
import os
from pathlib import Path
import statistics as st

ARCHIVE = Path("/mnt/d/fabric-d2/caliper-workspace")  # current reports
TARGET_SEEDS = [1, 2, 3, 4, 5]
ROUNDS = ["rate-100", "rate-500", "rate-1000", "rate-2000"]

# Regex to find table rows: <td>name</td> <td>succ</td> <td>fail</td> <td>send_rate</td> <td>max_lat</td> <td>min_lat</td> <td>avg_lat</td> <td>throughput</td>
ROW_RE = re.compile(
    r"<td>(rate-\d+)</td>\s*<td>([\d.-]+)</td>\s*<td>([\d.-]+)</td>\s*<td>([\d.-]+)</td>\s*<td>([\d.-]+|-)</td>\s*<td>([\d.-]+|-)</td>\s*<td>([\d.-]+|-)</td>\s*<td>([\d.-]+)</td>"
)

def parse_report(path):
    text = path.read_text(encoding="utf-8")
    rows = ROW_RE.findall(text)
    seen = set()
    result = {}
    for m in rows:
        name = m[0]
        if name in seen:
            continue
        seen.add(name)
        result[name] = {
            "succ": int(m[1]),
            "fail": int(m[2]),
            "send_rate": float(m[3]),
            "max_lat": None if m[4] == "-" else float(m[4]),
            "min_lat": None if m[5] == "-" else float(m[5]),
            "avg_lat": None if m[6] == "-" else float(m[6]),
            "throughput": float(m[7]),
        }
    return result

per_seed = {}
for s in TARGET_SEEDS:
    f = ARCHIVE / f"report-seed{s}.html"
    if not f.exists():
        print(f"[skip] seed {s}: no report")
        continue
    per_seed[s] = parse_report(f)

print("\n=== Per-seed per-round summary ===")
print(f"{'seed':>4}  {'round':>9}  {'succ':>6}  {'fail':>6}  {'send':>7}  {'thr':>7}  {'avg_lat':>7}  {'max_lat':>7}")
for s in sorted(per_seed):
    for r in ROUNDS:
        if r not in per_seed[s]:
            print(f"{s:>4}  {r:>9}  (not run)")
            continue
        d = per_seed[s][r]
        avg = "-" if d["avg_lat"] is None else f"{d['avg_lat']:.3f}"
        mx = "-" if d["max_lat"] is None else f"{d['max_lat']:.3f}"
        print(f"{s:>4}  {r:>9}  {d['succ']:>6}  {d['fail']:>6}  {d['send_rate']:>7.1f}  {d['throughput']:>7.1f}  {avg:>7}  {mx:>7}")

print("\n=== Aggregate across seeds (mean ± std) ===")
print(f"{'round':>9}  {'succ_mean':>10}  {'fail_mean':>10}  {'thr_mean':>9}  {'thr_std':>8}  {'avg_lat_mean':>13}  {'n':>3}")
for r in ROUNDS:
    succ = [per_seed[s][r]["succ"] for s in per_seed if r in per_seed[s]]
    fail = [per_seed[s][r]["fail"] for s in per_seed if r in per_seed[s]]
    thr = [per_seed[s][r]["throughput"] for s in per_seed if r in per_seed[s]]
    lat = [per_seed[s][r]["avg_lat"] for s in per_seed if r in per_seed[s] and per_seed[s][r]["avg_lat"] is not None]
    if not thr:
        continue
    print(f"{r:>9}  {st.mean(succ):>10.0f}  {st.mean(fail):>10.0f}  {st.mean(thr):>9.1f}  {st.stdev(thr) if len(thr)>1 else 0:>8.2f}  {(st.mean(lat) if lat else 0):>13.3f}  {len(thr):>3d}")
