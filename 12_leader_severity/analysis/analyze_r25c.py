# R25C analysis, written before the data was read.
# Implements PREREG_R25C sections 3-5 exactly: primary endpoint, secondaries,
# median with a 10,000-resample percentile bootstrap, and the two gates.
import io, os, re, glob, random

RES = "D:/fabric-d2/results"
ARMS = ["C_clean", "F_follower", "L_leader", "C_clean_post"]
RATES = [100, 200, 300, 400, 500]
PRIMARY_RATE = 500

row_re = re.compile(
    r"\|\s*rate-(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([\d.]+)\s*\|"
    r"\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*([\d.]+)\s*\|")


def parse_run(d):
    """summary.txt -> {arm: {rate: dict}}; arms appear in file order."""
    p = os.path.join(d, "summary.txt")
    if not os.path.exists(p):
        return None
    txt = io.open(p, encoding="utf-8", errors="replace").read()
    out, arm = {}, None
    for line in txt.splitlines():
        m = re.match(r"=====\s*(\w+)", line.strip())
        if m and m.group(1) in ARMS:
            arm = m.group(1)
            out.setdefault(arm, {})
            continue
        r = row_re.search(line)
        if r and arm:
            rate = int(r.group(1))
            # a rate can be echoed twice (per-round then summary); keep the first
            if rate in out[arm]:
                continue
            out[arm][rate] = dict(
                succ=int(r.group(2)), fail=int(r.group(3)),
                send=float(r.group(4)), maxlat=float(r.group(5)),
                minlat=float(r.group(6)), avglat=float(r.group(7)),
                tput=float(r.group(8)))
    return out


def boot_ci(vals, n=10000, seed=20260824):
    if len(vals) < 2:
        return (float("nan"), float("nan"))
    rnd = random.Random(seed)
    meds = []
    k = len(vals)
    for _ in range(n):
        s = sorted(vals[rnd.randrange(k)] for _ in range(k))
        meds.append(s[k // 2] if k % 2 else (s[k // 2 - 1] + s[k // 2]) / 2.0)
    meds.sort()
    return (meds[int(0.025 * n)], meds[int(0.975 * n) - 1])


def median(v):
    s = sorted(v); k = len(s)
    if k == 0: return float("nan")
    return s[k // 2] if k % 2 else (s[k // 2 - 1] + s[k // 2]) / 2.0


dirs = sorted(glob.glob(os.path.join(RES, "r25c_2*")))
runs = []
for d in dirs:
    parsed = parse_run(d)
    if not parsed:
        continue
    need = ("C_clean", "F_follower", "L_leader")
    ok = all(a in parsed and PRIMARY_RATE in parsed[a] for a in need)
    runs.append((os.path.basename(d), parsed, ok))

valid = [(n, p) for n, p, ok in runs if ok]
invalid = [n for n, p, ok in runs if not ok]

print("=" * 74)
print("R25C  --  what a degraded LEADER costs (N=7, +200 ms, bracketed)")
print("=" * 74)
print("attempts parsed : %d" % len(runs))
print("VALID runs      : %d" % len(valid))
print("invalid         : %d" % len(invalid))
print()

if not valid:
    print("no valid run yet -- nothing to report")
    raise SystemExit(0)

# ---------------- per-run table, primary rate ----------------
print("-" * 74)
print("Per run, at offered %d tx/s" % PRIMARY_RATE)
print("-" * 74)
hdr = "%-22s %8s %8s %8s %7s %7s %8s" % (
    "run", "clean", "follow", "leader", "R", "Rf", "fail%")
print(hdr)
Rs, Rfs, Ds, fails, latr = [], [], [], [], []
for name, p in valid:
    c = p["C_clean"][PRIMARY_RATE]
    f = p["F_follower"][PRIMARY_RATE]
    l = p["L_leader"][PRIMARY_RATE]
    R = l["tput"] / c["tput"]
    Rf = f["tput"] / c["tput"]
    ff = 100.0 * l["fail"] / max(1, l["succ"] + l["fail"])
    Rs.append(R); Rfs.append(Rf); fails.append(ff)
    latr.append(l["avglat"] / c["avglat"] if c["avglat"] else float("nan"))
    if "C_clean_post" in p and PRIMARY_RATE in p["C_clean_post"]:
        Ds.append(p["C_clean_post"][PRIMARY_RATE]["tput"] / c["tput"])
    print("%-22s %8.1f %8.1f %8.1f %7.3f %7.3f %7.1f%%" % (
        name.replace("r25c_", ""), c["tput"], f["tput"], l["tput"], R, Rf, ff))

# ---------------- primary endpoint ----------------
print()
print("-" * 74)
print("PRIMARY  R = throughput(L_leader) / throughput(C_clean)  at %d tx/s" % PRIMARY_RATE)
print("-" * 74)
mR = median(Rs); lo, hi = boot_ci(Rs)
half = (hi - lo) / 2.0
print("  median R        = %.4f      (a %.1f%% loss of committed throughput)" % (mR, 100 * (1 - mR)))
print("  95%% bootstrap CI = [%.4f, %.4f]   half-width %.4f" % (lo, hi, half))
print("  per-run R       = %s" % ", ".join("%.3f" % x for x in Rs))

print()
print("SECONDARY")
print("  median Rf (follower delay)   = %.4f   (%.1f%% loss)" % (median(Rfs), 100 * (1 - median(Rfs))))
print("  median failure fraction      = %.1f%%" % median(fails))
print("  median latency ratio L/C     = %.1fx" % median(latr))
if Ds:
    print("  median bracket drift D       = %.4f   (range %.4f-%.4f, n=%d)" % (
        median(Ds), min(Ds), max(Ds), len(Ds)))
else:
    print("  bracket drift D              = no bracket completed")

# ---------------- per-rate curve ----------------
print()
print("-" * 74)
print("Median R by offered rate")
print("-" * 74)
for rate in RATES:
    vals = []
    for _, p in valid:
        if all(rate in p.get(a, {}) for a in ("C_clean", "L_leader")):
            cc = p["C_clean"][rate]["tput"]
            if cc:
                vals.append(p["L_leader"][rate]["tput"] / cc)
    if vals:
        print("  %3d tx/s : median R = %.3f   (n=%d)" % (rate, median(vals), len(vals)))

# ---------------- pre-registered gates ----------------
print()
print("=" * 74)
print("PRE-REGISTERED DECISIONS")
print("=" * 74)
print("  falsification (PREREG sec.8): withdraw the claim if median R > 0.8")
if mR > 0.8:
    print("    -> median R = %.3f  ** CLAIM FAILS ** severity paragraph is withdrawn" % mR)
elif mR > 0.5:
    print("    -> median R = %.3f  direction holds, but 'stops it' must go" % mR)
else:
    print("    -> median R = %.3f  claim stands" % mR)

print()
print("  sample size (PREREG sec.5): at 12 valid runs, extend to 18 iff")
print("  the 95%% CI half-width on median R exceeds 0.05")
if len(valid) < 12:
    print("    -> %d valid so far; this gate is evaluated at 12, not now" % len(valid))
    print("       (current half-width %.4f is informational only)" % half)
else:
    print("    -> half-width %.4f -> %s" % (half, "EXTEND to 18" if half > 0.05 else "STOP at 12"))

if Ds and median(Ds) < 0.90:
    print()
    print("  drift (PREREG sec.4): median D = %.3f < 0.90 -- the fixed arm order is a" % median(Ds))
    print("  material confound and R must be reported with that stated.")
