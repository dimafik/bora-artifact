#!/usr/bin/env python3
"""Full report for one X1 run directory (results/x1_N*/).

PRIMARY metric: candidacy suppression.  Whether a blacklisted orderer still
*attempts* to campaign is a direct, dense observation of Algorithm 2's tick
guard.  The N=11 pilot showed why this matters: across 30 forced elections the
win-rate was 0/10 in every arm, so the outcome metric could not distinguish
"BORA worked" from "the degraded node would not have won anyway", while campaign
attempts separated cleanly (targets 1.00/node in vanilla, 0.00 under guard, with
non-targets unchanged).

SECONDARY metric: leadership win rate, kept for continuity with the published
single-target numbers and reported with honest Wilson intervals.

AUDIT: the cap rule |B_t| < f - r, checked at the mid-pause snapshot where r=1,
which is the only moment the rule actually binds during a forced election.

    python3 x1_analyze.py [run_dir]
"""
import csv, glob, os, re, subprocess, sys, datetime, collections
from math import comb, exp

ARMS = ("A_vanilla", "B_oracle", "C_predictor")


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p, d = k / n, 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return (max(0.0, c - h), min(1.0, c + h))


def fisher_greater(a, b, c, d):
    """One-sided p that arm1 has MORE wins than arm2, table [[a,b],[c,d]]."""
    n = a + b + c + d
    if n == 0:
        return 1.0
    p = 0.0
    for i in range(a, min(a + b, a + c) + 1):
        k = a + c - i
        if k < 0 or a + b - i < 0 or d - (i - a) < 0:
            continue
        p += comb(a + b, i) * comb(c + d, k) / comb(n, a + c)
    return min(1.0, p)


run = sys.argv[1] if len(sys.argv) > 1 else sorted(glob.glob("D:/fabric-d2/results/x1_N*"))[-1]
run = run.rstrip("/\\")
rows = list(csv.DictReader(open(os.path.join(run, "elections.csv"))))
if not rows:
    sys.exit("no elections recorded")

N = int(rows[0]["N"]); F = int(rows[0]["f"]); M = int(rows[0]["m"])
targets = {int(t) for t in rows[0]["targets"].replace(",", ";").split(";") if t.strip()}
chance = M / (N - 1)

print("=" * 72)
print("X1  %s" % os.path.basename(run))
print("N=%d  f=%d  m=%d  targets=%s   analytic chance share=%.1f%%   elections=%d"
      % (N, F, M, sorted(targets), 100 * chance, len(rows)))
print("=" * 72)

# ---------------------------------------------------------------- window helper
win = {}
for arm in ARMS:
    r = [x for x in rows if x["arm"] == arm]
    if r:
        win[arm] = (min(float(x["t_start"]) for x in r),
                    max(float(x.get("t_end") or x["t_start"]) for x in r), len(r))


# ---------------------------------------------------------------- PRIMARY
def campaign_times(i, arm_tag_glob):
    """Distinct campaign timestamps for node i, from saved logs when available."""
    saved = sorted(glob.glob(os.path.join(run, "logs", "%s_orderer%d.log" % (arm_tag_glob, i))))
    text = ""
    if saved:
        for p in saved:
            text += open(p, errors="replace").read()
    else:
        h = "orderer.example.com" if i == 1 else "orderer%d.example.com" % i
        try:
            o = subprocess.run(["docker", "logs", h], capture_output=True, text=True,
                               errors="replace", timeout=120)
            text = o.stdout + o.stderr
        except Exception:
            return set()
    # Match on the trailing "node=<decimal>" field, NOT on the id after "->".
    # etcd/raft prints raft ids in HEX, so orderer10 logs "campaign -> a [...]".
    # A decimal pattern therefore silently found zero campaigns for every node
    # from 10 upward -- including nodes that demonstrably won elections. The
    # node= suffix is decimal and identifies the node that emitted the line,
    # which for a campaign line is the node campaigning.
    pat = re.compile(r"(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2})\.\d+ UTC.*campaign.*node=%d\b" % i)
    out = set()
    for line in text.splitlines():
        m = pat.search(line)
        if m:
            t = datetime.datetime.strptime(m.group(1) + " " + m.group(2), "%Y-%m-%d %H:%M:%S")
            out.add(t.replace(tzinfo=datetime.timezone.utc).timestamp())
    return out


print("\n### PRIMARY - candidacy suppression (campaign attempts per node)\n")
allc = {i: campaign_times(i, "*") for i in range(1, N + 1)}
cnt = collections.defaultdict(dict)
for i in range(1, N + 1):
    for arm, (t0, t1, _) in win.items():
        cnt[i][arm] = sum(1 for t in allc[i] if t0 <= t <= t1 + 5)

hdr = "%-11s %-8s" % ("node", "role") + "".join("%-14s" % a for a in win)
print(hdr); print("-" * len(hdr))
agg = {a: [0, 0] for a in win}
for i in range(1, N + 1):
    line = "%-11s %-8s" % ("orderer%d" % i, "TARGET" if i in targets else "-")
    for arm in win:
        line += "%-14d" % cnt[i][arm]
        agg[arm][0 if i in targets else 1] += cnt[i][arm]
    print(line)
print("-" * len(hdr))
nt = N - len(targets)
print("%-11s %-8s" % ("per-node", "TARGET") + "".join("%-14.2f" % (agg[a][0] / len(targets)) for a in win))
print("%-11s %-8s" % ("per-node", "other") + "".join("%-14.2f" % (agg[a][1] / nt) for a in win))

# Poisson test: under the null, a blacklisted node campaigns at the same per-node
# rate as the healthy nodes in the same arm.
print()
for arm in win:
    if arm == "A_vanilla":
        continue
    rate = agg[arm][1] / nt
    exp_t = rate * len(targets)
    obs = agg[arm][0]
    if obs == 0 and exp_t > 0:
        print("  %-12s targets expected %.1f campaigns at the healthy-node rate, observed 0"
              "   ->  p = e^-%.1f = %.4g" % (arm, exp_t, exp_t, exp(-exp_t)))
    else:
        print("  %-12s targets expected %.1f, observed %d" % (arm, exp_t, obs))

# ---------------------------------------------------------------- SECONDARY
print("\n### SECONDARY - leadership win rate (kept for continuity)\n")
tally = {}
for arm in ARMS:
    r = [x for x in rows if x["arm"] == arm]
    if not r:
        continue
    n = len(r)
    won = sum(int(x["target_won"]) for x in r)
    live = sum(int(x["live"]) for x in r)
    lbt = sum(int(x["lb_was_target"]) for x in r)
    w = collections.Counter(x["window"] for x in r)
    lo, hi = wilson(won, n)
    print("  %-12s win %2d/%-3d = %5.1f%%  95%% CI [%.1f, %.1f]%%  (chance %.1f%%)  live %d/%d"
          % (arm, won, n, 100 * won / n, 100 * lo, 100 * hi, 100 * chance, live, n))
    print("  %-12s window W0=%d Wp=%d W1=%d   paused leader was a target %d times"
          % ("", w["W0"], w["Wp"], w["W1"], lbt))
    tally[arm] = (won, n)
if "A_vanilla" in tally and "C_predictor" in tally:
    (wa, na), (wc, nc) = tally["A_vanilla"], tally["C_predictor"]
    p = fisher_greater(wa, na - wa, wc, nc - wc)
    print("\n  Fisher exact (A > C, one-sided): p = %.4f%s"
          % (p, "  *** significant" if p < 0.05 else "  (underpowered at this n)"))
    if wa == 0:
        print("  NOTE: the baseline arm produced zero wins, so this comparison carries")
        print("        no information regardless of n. Rely on the primary metric.")

# ---------------------------------------------------------------- AUDIT
print("\n### AUDIT - cap rule |B_t| < f - r\n")
for tag, rk, ck, sk in (("pre-pause  (r=0 expected)", "r", "cap", "size"),
                        ("mid-pause  (r=1 expected)", "r_mid", "cap_mid", "size_mid")):
    if rk not in rows[0]:
        print("  %-26s column absent (run predates the mid-pause snapshot)" % tag)
        continue
    checked = viol = 0
    rs = collections.Counter()
    for x in rows:
        try:
            r_, cap, size = int(x[rk]), int(x[ck]), int(x[sk])
        except (ValueError, KeyError):
            continue
        checked += 1
        rs[r_] += 1
        if cap != F - r_ - 1 or size > cap:
            viol += 1
    obs = ", ".join("r=%d x%d" % (k, v) for k, v in sorted(rs.items()))
    print("  %-26s %3d cycles, %d violations   [%s]" % (tag, checked, viol, obs or "none"))
