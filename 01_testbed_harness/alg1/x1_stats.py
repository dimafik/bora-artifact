#!/usr/bin/env python3
"""Supplementary statistics for the X1 main run.

The built-in report uses the healthy-node campaign rate as the null for target
campaigns.  The main run showed that null is wrong: delayed nodes campaign LESS
than healthy ones even with no guard at all (7.50 vs 12.44 per node in the
vanilla arm), because a 200 ms delay slows their vote exchange rather than
speeding up their timeout.  The correct null for "does the guard suppress
candidacy" is the TARGETS' OWN vanilla rate.

Also pools the two guarded arms against vanilla for the win rate, since B and C
test the same hypothesis (a blacklisted node must not take leadership).
"""
import csv, glob, os, sys, collections, re, datetime, subprocess
from math import comb, exp, lgamma


def fisher_greater(a, b, c, d):
    n = a + b + c + d
    p = 0.0
    for i in range(a, min(a + b, a + c) + 1):
        k = a + c - i
        if k < 0 or a + b - i < 0 or d - (i - a) < 0:
            continue
        p += comb(a + b, i) * comb(c + d, k) / comb(n, a + c)
    return min(1.0, p)


def pois_le(k, lam):
    """P(X <= k) for Poisson(lam)."""
    return sum(exp(-lam + i * __import__("math").log(lam) - lgamma(i + 1)) for i in range(k + 1))


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p, d = k / n, 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return (max(0.0, c - h), min(1.0, c + h))


run = sys.argv[1] if len(sys.argv) > 1 else sorted(glob.glob("D:/fabric-d2/results/x1_N11_*"))[-1]
run = run.rstrip("/\\")
rows = list(csv.DictReader(open(os.path.join(run, "elections.csv"))))
N = int(rows[0]["N"]); M = int(rows[0]["m"])
targets = {int(t) for t in rows[0]["targets"].replace(",", ";").split(";") if t.strip()}

print("=" * 70)
print("X1 supplementary statistics -- %s" % os.path.basename(run))
print("=" * 70)

# ---------------------------------------------------------------- win rate
print("\n[1] Leadership win rate\n")
tot = {}
for arm in ("A_vanilla", "B_oracle", "C_predictor"):
    r = [x for x in rows if x["arm"] == arm]
    w = sum(int(x["target_won"]) for x in r)
    lbt = sum(int(x["lb_was_target"]) for x in r)
    # elections the target could not possibly win: it was the paused leader
    elig = [x for x in r if x["lb_was_target"] == "0"]
    we = sum(int(x["target_won"]) for x in elig)
    lo, hi = wilson(w, len(r))
    lo2, hi2 = wilson(we, len(elig))
    tot[arm] = (w, len(r), we, len(elig))
    print("  %-12s %2d/%-3d = %5.1f%%  CI[%.1f,%.1f]%%   |  target-was-paused-leader excluded: %d/%d = %.1f%% CI[%.1f,%.1f]%%"
          % (arm, w, len(r), 100 * w / len(r), 100 * lo, 100 * hi,
             we, len(elig), 100 * we / len(elig), 100 * lo2, 100 * hi2))

wa, na, wae, nae = tot["A_vanilla"]
wb, nb, _, _ = tot["B_oracle"]
wc, nc, _, _ = tot["C_predictor"]
print()
print("  A vs C            : %d/%d vs %d/%d   Fisher one-sided p = %.4f"
      % (wa, na, wc, nc, fisher_greater(wa, na - wa, wc, nc - wc)))
print("  A vs B            : %d/%d vs %d/%d   Fisher one-sided p = %.4f"
      % (wa, na, wb, nb, fisher_greater(wa, na - wa, wb, nb - wb)))
print("  A vs (B+C) pooled : %d/%d vs %d/%d   Fisher one-sided p = %.4f"
      % (wa, na, wb + wc, nb + nc, fisher_greater(wa, na - wa, wb + wc, nb + nc - wb - wc)))

# ---------------------------------------------------------------- campaigns
print("\n[2] Campaign attempts -- correct null is the targets' own vanilla rate\n")
win = {}
for arm in ("A_vanilla", "B_oracle", "C_predictor"):
    r = [x for x in rows if x["arm"] == arm]
    win[arm] = (min(float(x["t_start"]) for x in r),
                max(float(x.get("t_end") or x["t_start"]) for x in r))


def camps(i):
    txt = ""
    for p in glob.glob(os.path.join(run, "logs", "*_orderer%d.log" % i)):
        txt += open(p, errors="replace").read()
    if not txt:
        h = "orderer.example.com" if i == 1 else "orderer%d.example.com" % i
        try:
            o = subprocess.run(["docker", "logs", h], capture_output=True, text=True,
                               errors="replace", timeout=120)
            txt = o.stdout + o.stderr
        except Exception:
            return set()
    # See x1_analyze.py: raft ids are printed in hex, so match the decimal
    # "node=" suffix instead of the id after "->".
    pat = re.compile(r"(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2})\.\d+ UTC.*campaign.*node=%d\b" % i)
    s = set()
    for line in txt.splitlines():
        m = pat.search(line)
        if m:
            t = datetime.datetime.strptime(m.group(1) + " " + m.group(2), "%Y-%m-%d %H:%M:%S")
            s.add(t.replace(tzinfo=datetime.timezone.utc).timestamp())
    return s


C = {i: camps(i) for i in range(1, N + 1)}
per = {}
for arm, (t0, t1) in win.items():
    tg = sum(len([t for t in C[i] if t0 <= t <= t1 + 5]) for i in targets)
    ot = sum(len([t for t in C[i] if t0 <= t <= t1 + 5]) for i in range(1, N + 1) if i not in targets)
    per[arm] = (tg, ot)
    print("  %-12s targets %3d   others %3d   (per node: %.2f vs %.2f)"
          % (arm, tg, ot, tg / len(targets), ot / (N - len(targets))))

base = per["A_vanilla"][0]
print()
print("  Null: a guarded target campaigns at its OWN vanilla rate (lambda = %d per arm)" % base)
for arm in ("B_oracle", "C_predictor"):
    obs = per[arm][0]
    print("    %-12s observed %3d   P(X <= %d | lambda=%d) = %.4f%s"
          % (arm, obs, obs, base, pois_le(obs, base),
             "  *" if pois_le(obs, base) < 0.05 else ""))
pooled = per["B_oracle"][0] + per["C_predictor"][0]
print("    %-12s observed %3d   P(X <= %d | lambda=%d) = %.4f%s"
      % ("B+C pooled", pooled, pooled, 2 * base, pois_le(pooled, 2 * base),
         "  *" if pois_le(pooled, 2 * base) < 0.05 else ""))

print()
print("  NOTE: in the vanilla arm the targets already campaign less than the")
print("  healthy nodes (%.2f vs %.2f per node). The 200 ms delay slows their vote"
      % (per["A_vanilla"][0] / len(targets), per["A_vanilla"][1] / (N - len(targets))))
print("  exchange; it does not make them time out early. Using the healthy-node")
print("  rate as the null would therefore overstate the suppression effect.")
