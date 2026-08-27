# Did the testbed itself change partway through R25D, and what does that do to
# the registered endpoint? Sensitivity analysis, clearly post-hoc.
import io, os, re, glob
from math import sqrt

RES = "D:/fabric-d2/results"
ARMS = ["C_clean", "F_follower", "L_leader", "C_clean_post"]
RATE = 500
STALL = 0.50
HEALTHY_BASELINE = 450.0     # C_clean at 500 tx/s; the stable value was ~468

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


def wilson(k, n, z=1.959964):
    if n == 0: return (float("nan"),) * 2
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = (z / d) * sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, c - h) * 100, min(1.0, c + h) * 100)


def median(v):
    s = sorted(v); k = len(s)
    return float("nan") if not k else (s[k // 2] if k % 2 else (s[k//2-1]+s[k//2])/2.0)


rows = []
for d in sorted(glob.glob(os.path.join(RES, "r25c_2*"))):
    p = parse(d)
    if not p: continue
    if not all(a in p and RATE in p[a] for a in ("C_clean", "F_follower", "L_leader")):
        continue
    c = p["C_clean"][RATE]; l = p["L_leader"][RATE]
    ff = l["fail"] / max(1, l["succ"] + l["fail"])
    rows.append(dict(name=os.path.basename(d)[5:], clean=c["tput"], leader=l["tput"],
                     R=l["tput"] / c["tput"], ff=ff, stall=ff > STALL,
                     healthy=c["tput"] >= HEALTHY_BASELINE))

H = [r for r in rows if r["healthy"]]
C = [r for r in rows if not r["healthy"]]

print("=" * 74)
print("TESTBED REGIME CHECK  (post-hoc; not part of PREREG_R25D)")
print("=" * 74)
print("The registered analysis assumes one testbed. The clean arm says otherwise.")
print()
print("  healthy baseline (C_clean >= %.0f tx/s) : %2d runs" % (HEALTHY_BASELINE, len(H)))
print("  collapsed baseline                       : %2d runs" % len(C))
print()
print("  clean arm, healthy   : median %.1f tx/s  (range %.1f-%.1f)" % (
    median([r["clean"] for r in H]), min(r["clean"] for r in H), max(r["clean"] for r in H)))
print("  clean arm, collapsed : median %.1f tx/s  (range %.1f-%.1f)" % (
    median([r["clean"] for r in C]), min(r["clean"] for r in C), max(r["clean"] for r in C)))
print()
print("  leader arm, healthy   : median %.1f tx/s" % median([r["leader"] for r in H]))
print("  leader arm, collapsed : median %.1f tx/s" % median([r["leader"] for r in C]))
print()
print("  -> the leader arm barely moves; it is the BASELINE that fell to meet it,")
print("     which is why R looks better in the collapsed runs (%.3f vs %.3f)." % (
    median([r["R"] for r in C]), median([r["R"] for r in H])))

print()
print("=" * 74)
print("STALL PROPORTION, three ways")
print("=" * 74)
for lab, s in (("registered, all 36", rows), ("healthy baseline only", H), ("collapsed only", C)):
    k = sum(1 for r in s if r["stall"]); n = len(s)
    lo, hi = wilson(k, n)
    print("  %-22s %2d/%2d = %5.1f%%   95%% CI [%.1f%%, %.1f%%]" % (
        lab, k, n, 100.0 * k / n, lo, hi))

print()
print("R MEDIAN, three ways")
for lab, s in (("registered, all 36", rows), ("healthy baseline only", H), ("collapsed only", C)):
    print("  %-22s median R = %.4f  (n=%d)" % (lab, median([r["R"] for r in s]), len(s)))

print()
print("WHEN DID IT CHANGE")
prev = None
for r in rows:
    state = "healthy" if r["healthy"] else "COLLAPSED"
    if state != prev:
        print("    %s  ->  %s   (clean %.1f tx/s)" % (r["name"], state, r["clean"]))
        prev = state
