# What discretely separates a stalling run from a degrading one?
# Candidates: leadership retention through the arm, and the per-rate shape
# (a run that recovers mid-arm should climb; one that never recovers should not).
import io, os, re, glob, csv

RES = "D:/fabric-d2/results"
ARMS = ["C_clean", "F_follower", "L_leader", "C_clean_post"]
RATES = [100, 200, 300, 400, 500]
STALL = 0.50

row_re = re.compile(
    r"\|\s*rate-(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([\d.]+)\s*\|"
    r"\s*([\d.-]+)\s*\|\s*([\d.-]+)\s*\|\s*([\d.-]+)\s*\|\s*([\d.]+)\s*\|")


def parse(d):
    p = os.path.join(d, "summary.txt")
    if not os.path.exists(p): return None
    txt = io.open(p, encoding="utf-8", errors="replace").read()
    out, arm = {}, None
    for line in txt.splitlines():
        m = re.match(r"=====\s*(\w+)", line.strip())
        if m and m.group(1) in ARMS:
            arm = m.group(1); out.setdefault(arm, {}); continue
        r = row_re.search(line)
        if r and arm:
            rt = int(r.group(1))
            if rt in out[arm]: continue
            out[arm][rt] = dict(succ=int(r.group(2)), fail=int(r.group(3)),
                                tput=float(r.group(8)))
    return out


def pin_attempt(d):
    """how many restarts were needed to pin orderer3, and the leader after"""
    p = os.path.join(d, "summary.txt")
    txt = io.open(p, encoding="utf-8", errors="replace").read()
    m = re.search(r"attempt (\d+): orderer3 IS LEADER", txt)
    n = re.search(r"leader right after attack starts: (\d+)", txt)
    return (int(m.group(1)) if m else None, n.group(1) if n else "?")


def arms_csv(d):
    p = os.path.join(d, "arms.csv"); out = {}
    if not os.path.exists(p): return out
    for r in csv.DictReader(io.open(p, encoding="utf-8", errors="replace")):
        out[r.get("arm", "")] = r
    return out


rows = []
for d in sorted(glob.glob(os.path.join(RES, "r25c_2*"))):
    p = parse(d)
    if not p: continue
    if not all(a in p and 500 in p[a] for a in ("C_clean", "F_follower", "L_leader")):
        continue
    if p["C_clean"][500]["tput"] < 450:
        continue
    L = p["L_leader"]
    ff = L[500]["fail"] / max(1, L[500]["succ"] + L[500]["fail"])
    tries, after = pin_attempt(d)
    a = arms_csv(d).get("L_leader", {})
    rows.append(dict(name=os.path.basename(d)[5:], stall=ff > STALL, L=L,
                     tries=tries, after=after,
                     lb=a.get("leader_before", "?"), la=a.get("leader_after", "?"),
                     secs=a.get("secs", "?")))

print("=" * 88)
print("L_leader throughput by offered rate  (verified-baseline runs)")
print("=" * 88)
print("%-16s %6s %7s %7s %7s %7s %7s | %4s %4s %5s %5s" % (
    "run", "mode", "100", "200", "300", "400", "500", "pin", "ldr", "b->a", "secs"))
for r in rows:
    v = [("%.1f" % r["L"][x]["tput"]) if x in r["L"] else "-" for x in RATES]
    print("%-16s %6s %7s %7s %7s %7s %7s | %4s %4s %2s>%-2s %5s" % (
        r["name"], "STALL" if r["stall"] else "degr.", *v,
        r["tries"], r["after"], r["lb"], r["la"], r["secs"]))

print()
print("=" * 88)
print("PER-RATE FAILURE FRACTION  (does a degrading run recover mid-arm?)")
print("=" * 88)
print("%-16s %6s %7s %7s %7s %7s %7s" % ("run", "mode", "100", "200", "300", "400", "500"))
for r in rows:
    v = []
    for x in RATES:
        if x in r["L"]:
            c = r["L"][x]
            v.append("%.0f%%" % (100.0 * c["fail"] / max(1, c["succ"] + c["fail"])))
        else:
            v.append("-")
    print("%-16s %6s %7s %7s %7s %7s %7s" % (
        r["name"], "STALL" if r["stall"] else "degr.", *v))

print()
print("=" * 88)
print("SUMMARY")
print("=" * 88)
st = [r for r in rows if r["stall"]]; dg = [r for r in rows if not r["stall"]]
for lab, s in (("STALL", st), ("degr.", dg)):
    if not s: continue
    tri = [r["tries"] for r in s if r["tries"]]
    sec = [int(r["secs"]) for r in s if str(r["secs"]).isdigit()]
    print("  %-6s n=%2d | pin attempts %s | arm secs median %s | leader after: %s" % (
        lab, len(s),
        ("%.1f avg" % (sum(tri) / len(tri))) if tri else "?",
        sorted(sec)[len(sec) // 2] if sec else "?",
        ",".join(sorted(set(r["la"] for r in s)))))
