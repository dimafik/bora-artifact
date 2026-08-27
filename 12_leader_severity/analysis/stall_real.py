# Is the "stall" mode a real channel stop, or the client-side deadline artifact
# that belowceiling-sweep.yaml warns about?
#
# The test: Caliper counts a transaction failed when the gateway's commit-status
# call times out. The LEDGER does not lie. If a stalling arm still grows the
# ledger at a rate comparable to its reported successes, the failures are
# client-side and the channel did not stop.
import io, os, re, glob, csv

RES = "D:/fabric-d2/results"
ARMS = ["C_clean", "F_follower", "L_leader", "C_clean_post"]
RATE = 500
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


def arms_csv(d):
    p = os.path.join(d, "arms.csv"); out = {}
    if not os.path.exists(p): return out
    for r in csv.DictReader(io.open(p, encoding="utf-8", errors="replace")):
        try:
            out[r["arm"]] = dict(h0=int(r["h0"]), h1=int(r["h1"]), secs=int(r["secs"]))
        except Exception:
            pass
    return out


rows = []
for d in sorted(glob.glob(os.path.join(RES, "r25c_2*"))):
    p = parse(d); a = arms_csv(d)
    if not p or "L_leader" not in a: continue
    if not all(x in p and RATE in p[x] for x in ("C_clean", "F_follower", "L_leader")):
        continue
    if p["C_clean"][RATE]["tput"] < 450:      # verified-baseline runs only
        continue
    L = p["L_leader"]; C = p["C_clean"]
    lsucc = sum(L[r]["succ"] for r in L); lfail = sum(L[r]["fail"] for r in L)
    csucc = sum(C[r]["succ"] for r in C); cfail = sum(C[r]["fail"] for r in C)
    lblocks = a["L_leader"]["h1"] - a["L_leader"]["h0"]
    cblocks = a["C_clean"]["h1"] - a["C_clean"]["h0"]
    ff = L[RATE]["fail"] / max(1, L[RATE]["succ"] + L[RATE]["fail"])
    rows.append(dict(name=os.path.basename(d)[5:], stall=ff > STALL,
                     lsucc=lsucc, lfail=lfail, lblocks=lblocks,
                     csucc=csucc, cblocks=cblocks,
                     lsecs=a["L_leader"]["secs"], csecs=a["C_clean"]["secs"]))

print("=" * 82)
print("IS THE STALL REAL?  ledger growth vs Caliper's success count")
print("      (verified-baseline runs only, whole L_leader arm = 45,000 tx offered)")
print("=" * 82)
print("%-16s %6s %8s %8s %8s %9s %9s" % (
    "run", "mode", "succ", "fail", "blocks", "tx/block", "blk/s"))
for r in rows:
    tpb = r["lsucc"] / r["lblocks"] if r["lblocks"] else 0
    print("%-16s %6s %8d %8d %8d %9.2f %9.2f" % (
        r["name"], "STALL" if r["stall"] else "degr.",
        r["lsucc"], r["lfail"], r["lblocks"], tpb, r["lblocks"] / max(1, r["lsecs"])))

print()
print("-" * 82)
print("CLEAN ARM, same runs, for the tx-per-block reference")
print("-" * 82)
ref = [r["csucc"] / r["cblocks"] for r in rows if r["cblocks"]]
print("  clean arm tx/block: median %.2f  (range %.2f-%.2f)" % (
    sorted(ref)[len(ref) // 2], min(ref), max(ref)))
print("  clean arm blocks/s: median %.2f" % sorted(
    [r["cblocks"] / max(1, r["csecs"]) for r in rows])[len(rows) // 2])

print()
print("=" * 82)
print("VERDICT")
print("=" * 82)
st = [r for r in rows if r["stall"]]
dg = [r for r in rows if not r["stall"]]
for lab, s in (("STALL runs", st), ("degrading runs", dg)):
    if not s: continue
    b = sorted(r["lblocks"] for r in s)[len(s) // 2]
    su = sorted(r["lsucc"] for r in s)[len(s) // 2]
    bs = sorted(r["lblocks"] / max(1, r["lsecs"]) for r in s)[len(s) // 2]
    print("  %-15s median blocks %6d | median succ %6d | blocks/s %.2f" % (lab, b, su, bs))
print()
print("  If the STALL rows still commit blocks at a healthy rate while Caliper")
print("  reports ~0 successes, the channel did NOT stop: the failures are the")
print("  client-side DEADLINE_EXCEEDED artifact the benchmark config warns about.")
