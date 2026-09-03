#!/usr/bin/env python3
"""Mechanism-level audit for an X1 run: who actually campaigned, and when.

Outcome statistics alone cannot separate "BORA suppressed the degraded node"
from "the degraded node happened not to win".  The discriminating evidence is
whether a blacklisted node still *attempts* to campaign.  Algorithm 2's tick
guard is supposed to stop it at the source, so a target should campaign at a
normal rate in the vanilla arm and never in the guarded arms, while non-targets
keep campaigning throughout.

Counts distinct campaign events per orderer (one event = one burst of MsgPreVote
lines sharing a timestamp) and buckets them into the arm windows recorded in
elections.csv.

    python3 x1_campaign_audit.py [run_dir]
"""
import csv, glob, re, subprocess, sys, datetime, collections

run = sys.argv[1] if len(sys.argv) > 1 else sorted(glob.glob("D:/fabric-d2/results/x1_N11_*"))[-1]
rows = list(csv.DictReader(open(run + "/elections.csv")))
if not rows:
    sys.exit("no elections recorded")

N = int(rows[0]["N"])
targets = {int(t) for t in rows[0]["targets"].replace('"', "").split(",")}

# Per-ELECTION windows, not per-arm.  x1_closedloop.sh interleaves the arms
# (for each seed: A, then B, then C), so an arm's first-to-last span covers the
# other two almost entirely -- on x1_N7_20260810-112256 each arm spans 23 min
# while its elections occupy 40 x 13 s = 8.7 min, and B overlaps A by 91%.
# Bucketing on those spans counted every campaign into two or three arms at
# once.  Each election records its own t_start/t_end, so use them.
win = {}
for arm in ("A_vanilla", "B_oracle", "C_predictor"):
    r = [x for x in rows if x["arm"] == arm]
    if r:
        win[arm] = ([(float(x["t_start"]), float(x["t_end"])) for x in r], len(r))

day = datetime.datetime.utcfromtimestamp(float(rows[0]["t_start"])).strftime("%Y-%m-%d")


def host(i):
    return "orderer.example.com" if i == 1 else "orderer%d.example.com" % i


def campaigns(i):
    """Distinct campaign timestamps (epoch) emitted by node i."""
    try:
        out = subprocess.run(["docker", "logs", host(i)], capture_output=True, text=True,
                             errors="replace", timeout=90)
    except Exception:
        return []
    seen = set()
    # raft ids are printed in hex ("-> a" for node 10); match the decimal
    # node= suffix instead. See x1_analyze.py.
    pat = re.compile(r"(\d{2}:\d{2}:\d{2}\.\d+) UTC.*campaign.*node=%d\b" % i)
    for line in (out.stdout + out.stderr).splitlines():
        m = pat.search(line)
        if m:
            seen.add(m.group(1)[:8])
    res = []
    for hms in seen:
        t = datetime.datetime.strptime(day + " " + hms, "%Y-%m-%d %H:%M:%S")
        res.append(t.replace(tzinfo=datetime.timezone.utc).timestamp())
    return sorted(res)


print("=" * 70)
print("campaign audit   run=%s   N=%d   targets=%s" % (run.split("\\")[-1], N, sorted(targets)))
for a, (spans, n) in win.items():
    f = lambda t: datetime.datetime.utcfromtimestamp(t).strftime("%H:%M:%S")
    occ = sum(t1 - t0 for t0, t1 in spans)
    print("   %-12s %s ~ %s   (%d elections, %.1f min of election time)"
          % (a, f(spans[0][0]), f(spans[-1][1]), n, occ / 60.0))
print("=" * 70)

tab = collections.defaultdict(dict)
for i in range(1, N + 1):
    cs = campaigns(i)
    for arm, (spans, _) in win.items():
        tab[i][arm] = sum(1 for t in cs
                          if any(t0 <= t <= t1 for t0, t1 in spans))

hdr = "%-10s %-7s" % ("node", "role") + "".join("%-14s" % a for a in win)
print(hdr)
print("-" * len(hdr))
agg = {a: [0, 0] for a in win}          # [target campaigns, non-target campaigns]
for i in range(1, N + 1):
    role = "TARGET" if i in targets else "-"
    line = "%-10s %-7s" % ("orderer%d" % i, role)
    for arm in win:
        c = tab[i][arm]
        line += "%-14s" % c
        agg[arm][0 if i in targets else 1] += c
    print(line)
print("-" * len(hdr))
nt = N - len(targets)
print("%-10s %-7s" % ("SUM", "target") + "".join("%-14s" % agg[a][0] for a in win))
print("%-10s %-7s" % ("SUM", "other") + "".join("%-14s" % agg[a][1] for a in win))
print("%-10s %-7s" % ("per-node", "target") + "".join("%-14.2f" % (agg[a][0] / len(targets)) for a in win))
print("%-10s %-7s" % ("per-node", "other") + "".join("%-14.2f" % (agg[a][1] / nt) for a in win))
print()
print("Read: if the tick guard fires, the target row goes to 0 in B_oracle and")
print("C_predictor while the other row stays at its vanilla level.  A target that")
print("keeps campaigning while blacklisted means only the vote guard is active.")
