import re, os, statistics as st
from pathlib import Path

ARCHIVE = Path("/mnt/d/fabric-d2/results/archive/5node_caliper_clean_2026-06-07")
ROUNDS = ["rate-100", "rate-300", "rate-500"]
ROW_RE = re.compile(
    r"<td>(rate-\d+)</td>\s*<td>([\d.-]+)</td>\s*<td>([\d.-]+)</td>\s*<td>([\d.-]+)</td>\s*<td>([\d.-]+|-)</td>\s*<td>([\d.-]+|-)</td>\s*<td>([\d.-]+|-)</td>\s*<td>([\d.-]+)</td>"
)

ps = {}
for s in range(1, 6):
    f = ARCHIVE / f"report-clean-seed{s}.html"
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
            "thr": float(m[7]),
            "avg": None if m[6] == "-" else float(m[6]),
        }

print(f"{'seed':>4}  {'round':>9}  {'succ':>7}  {'fail':>5}  {'thr':>6}  {'avg_lat':>7}")
for s in sorted(ps):
    for r in ROUNDS:
        if r not in ps[s]:
            continue
        d = ps[s][r]
        lat = "-" if d["avg"] is None else f"{d['avg']:.3f}"
        print(f"{s:>4}  {r:>9}  {d['succ']:>7}  {d['fail']:>5}  {d['thr']:>6.1f}  {lat:>7}")

print()
print(f"{'round':>9}  {'thr_mean':>9}  {'thr_std':>8}  {'lat_mean':>9}  {'n_succ':>6}")
for r in ROUNDS:
    thr = [ps[s][r]["thr"] for s in ps if r in ps[s] and ps[s][r]["succ"] > 0]
    lat = [ps[s][r]["avg"] for s in ps if r in ps[s] and ps[s][r]["avg"] is not None]
    if not thr:
        continue
    m = st.mean(thr); sd = st.stdev(thr) if len(thr) > 1 else 0
    lm = st.mean(lat) if lat else 0
    print(f"{r:>9}  {m:>9.2f}  {sd:>8.2f}  {lm:>9.3f}  {len(thr):>6d}")
