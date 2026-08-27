# R25D analysis, written before the extension runs.
# Implements PREREG_R25D: stall proportion with a Wilson interval, the
# bimodality check, the aftermath asymmetry, and R re-reported for consistency.
import io, os, re, glob, random
from math import sqrt

RES = "D:/fabric-d2/results"
ARMS = ["C_clean", "F_follower", "L_leader", "C_clean_post"]
PRIMARY_RATE = 500
STALL_THRESHOLD = 0.50        # PREREG_R25D sec.2, fixed before the extension
GAP_LO, GAP_HI = 0.15, 0.95   # PREREG_R25D sec.5, the gap that must stay empty
TARGET = 36

row_re = re.compile(
    r"\|\s*rate-(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([\d.]+)\s*\|"
    r"\s*([\d.-]+)\s*\|\s*([\d.-]+)\s*\|\s*([\d.-]+)\s*\|\s*([\d.]+)\s*\|")


def parse(d):
    p = os.path.join(d, "summary.txt")
    if not os.path.exists(p):
        return None
    txt = io.open(p, encoding="utf-8", errors="replace").read()
    out, arm = {}, None
    for line in txt.splitlines():
        m = re.match(r"=====\s*(\w+)", line.strip())
        if m and m.group(1) in ARMS:
            arm = m.group(1); out.setdefault(arm, {}); continue
        r = row_re.search(line)
        if r and arm:
            rt = int(r.group(1))
            if rt in out[arm]:
                continue
            out[arm][rt] = dict(succ=int(r.group(2)), fail=int(r.group(3)),
                                avglat=r.group(7), tput=float(r.group(8)))
    return out


def wilson(k, n, z=1.959964):
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = (z / d) * sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (max(0.0, c - h) * 100, min(1.0, c + h) * 100)


def median(v):
    s = sorted(v); k = len(s)
    if not k: return float("nan")
    return s[k // 2] if k % 2 else (s[k // 2 - 1] + s[k // 2]) / 2.0


def boot_ci(vals, n=10000, seed=20260825):
    if len(vals) < 2: return (float("nan"), float("nan"))
    rnd = random.Random(seed); k = len(vals); meds = []
    for _ in range(n):
        s = sorted(vals[rnd.randrange(k)] for _ in range(k))
        meds.append(s[k // 2] if k % 2 else (s[k // 2 - 1] + s[k // 2]) / 2.0)
    meds.sort()
    return (meds[int(0.025 * n)], meds[int(0.975 * n) - 1])


runs = []
for d in sorted(glob.glob(os.path.join(RES, "r25c_2*"))):
    p = parse(d)
    if not p:
        continue
    if all(a in p and PRIMARY_RATE in p[a] for a in ("C_clean", "F_follower", "L_leader")):
        runs.append((os.path.basename(d)[5:], p))

print("=" * 76)
print("R25D  --  how often does a degraded leader STALL the channel?")
print("      (PREREG_R25D: stall = L_leader failure fraction > %.2f at %d tx/s)"
      % (STALL_THRESHOLD, PRIMARY_RATE))
print("=" * 76)
print("valid runs pooled (R25C + extension) : %d / %d" % (len(runs), TARGET))
print()

if not runs:
    raise SystemExit(0)

rows = []
for name, p in runs:
    c = p["C_clean"][PRIMARY_RATE]
    f = p["F_follower"][PRIMARY_RATE]
    l = p["L_leader"][PRIMARY_RATE]
    po = p.get("C_clean_post", {}).get(PRIMARY_RATE)
    ff = l["fail"] / max(1, l["succ"] + l["fail"])
    rows.append(dict(name=name, R=l["tput"] / c["tput"], Rf=f["tput"] / c["tput"],
                     ff=ff, stall=ff > STALL_THRESHOLD,
                     D=(po["tput"] / c["tput"]) if po else None))

print("-" * 76)
print("%-16s %7s %7s %8s %8s %6s" % ("run", "R", "Rf", "L fail%", "D", "mode"))
print("-" * 76)
for r in rows:
    print("%-16s %7.3f %7.3f %7.1f%% %8s %6s" % (
        r["name"], r["R"], r["Rf"], 100 * r["ff"],
        ("%.3f" % r["D"]) if r["D"] is not None else "-",
        "STALL" if r["stall"] else "degr."))

k = sum(1 for r in rows if r["stall"]); n = len(rows)
lo, hi = wilson(k, n)
print()
print("=" * 76)
print("PRIMARY  stall proportion")
print("=" * 76)
print("  %d of %d runs stalled  =  %.1f%%" % (k, n, 100.0 * k / n))
print("  95%% Wilson CI = [%.1f%%, %.1f%%]   half-width %.1f pp" % (lo, hi, (hi - lo) / 2))
if n < TARGET:
    print("  (interim: the registered sample is %d, this is %d)" % (TARGET, n))

print()
print("BIMODALITY CHECK (PREREG sec.5/7)")
mid = [r for r in rows if GAP_LO <= r["ff"] <= GAP_HI]
if mid:
    print("  *** GAP FILLED: %d run(s) between %.0f%% and %.0f%% failure" % (
        len(mid), 100 * GAP_LO, 100 * GAP_HI))
    for r in mid:
        print("      %s  fail=%.1f%%" % (r["name"], 100 * r["ff"]))
    print("  -> the 'bimodal' description must be withdrawn (sec.7)")
else:
    fs = sorted(100 * r["ff"] for r in rows)
    dl = [x for x in fs if x < 100 * GAP_LO]
    dh = [x for x in fs if x > 100 * GAP_HI]
    print("  gap intact. degrading %.1f-%.1f%% (n=%d) | stalling %.1f-%.1f%% (n=%d)" % (
        (min(dl), max(dl), len(dl)) if dl else (0, 0, 0) +
        ((min(dh), max(dh), len(dh)) if dh else (0, 0, 0))) if False else
        "  gap intact. degrading %.1f-%.1f%% (n=%d) | stalling %.1f-%.1f%% (n=%d)" % (
            min(dl) if dl else 0, max(dl) if dl else 0, len(dl),
            min(dh) if dh else 0, max(dh) if dh else 0, len(dh)))

print()
print("AFTERMATH ASYMMETRY (PREREG sec.5)")
ds = [r["D"] for r in rows if r["stall"] and r["D"] is not None]
dd = [r["D"] for r in rows if not r["stall"] and r["D"] is not None]
if ds: print("  stalling runs   : median D = %.3f  (n=%d)" % (median(ds), len(ds)))
if dd: print("  degrading runs  : median D = %.3f  (n=%d)" % (median(dd), len(dd)))
if ds and dd:
    print("  -> stalling runs recover %s than degrading ones"
          % ("faster" if median(ds) > median(dd) else "slower"))

print()
print("SECONDARY  R over the pooled sample (consistency only, not a new decision)")
Rs = [r["R"] for r in rows]
mR = median(Rs); rlo, rhi = boot_ci(Rs)
print("  median R = %.4f   95%% CI [%.4f, %.4f]" % (mR, rlo, rhi))
print("  R25C reported 0.3553 with CI [0.2838, 0.3563]")
if not (0.2838 <= mR <= 0.3563):
    print("  *** median R has left the R25C interval -- report both, do not average (sec.7)")
else:
    print("  consistent with R25C")
