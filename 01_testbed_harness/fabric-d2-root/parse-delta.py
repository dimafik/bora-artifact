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
    if not f.exists():
        continue
    rows = ROW_RE.findall(f.read_text())
    seen = set()
    ps[s] = {}
    for m in rows:
        if m[0] in seen:
            continue
        seen.add(m[0])
        ps[s][m[0]] = {
            "succ": int(m[1]),
            "fail": int(m[2]),
            "send": float(m[3]),
            "max_lat": None if m[4] == "-" else float(m[4]),
            "avg": None if m[6] == "-" else float(m[6]),
            "thr": float(m[7]),
        }

print(f"\n{'seed':>4}  {'round':>9}  {'succ':>7}  {'fail':>6}  {'thr':>6}  {'avg_lat':>8}  {'max_lat':>8}")
for s in sorted(ps):
    for r in ROUNDS:
        if r not in ps[s]:
            continue
        d = ps[s][r]
        avg = "-" if d["avg"] is None else f"{d['avg']:.3f}"
        mx = "-" if d["max_lat"] is None else f"{d['max_lat']:.2f}"
        print(f"{s:>4}  {r:>9}  {d['succ']:>7}  {d['fail']:>6}  {d['thr']:>6.1f}  {avg:>8}  {mx:>8}")

print(f"\n{'round':>9}  {'thr_mean':>9}  {'thr_std':>8}  {'avg_lat_mean':>13}  {'succ_total':>11}  {'fail_total':>11}")
for r in ROUNDS:
    thrs = [ps[s][r]["thr"] for s in ps if r in ps[s]]
    lats = [ps[s][r]["avg"] for s in ps if r in ps[s] and ps[s][r]["avg"] is not None]
    succ = sum(ps[s][r]["succ"] for s in ps if r in ps[s])
    fail = sum(ps[s][r]["fail"] for s in ps if r in ps[s])
    if not thrs:
        continue
    m = st.mean(thrs); sd = st.stdev(thrs) if len(thrs) > 1 else 0
    lm = st.mean(lats) if lats else 0
    print(f"{r:>9}  {m:>9.2f}  {sd:>8.2f}  {lm:>13.3f}  {succ:>11d}  {fail:>11d}")
