#!/usr/bin/env python3
"""Per-target win breakdown, and whether leadership is uniform across nodes.

With m > 1 the aggregate win count can hide an asymmetry: if only one of the
degraded nodes ever wins, the "chance share m/(N-1)" framing overstates how many
nodes are really in play. This also checks the healthy nodes, because a skew
there would point at the harness (which node tends to be the paused leader)
rather than at anything about the targets.

    python3 x1_targets.py [run_dir ...]
"""
import csv, glob, os, re, sys, collections
from math import comb


def binom_tail(k, n, p):
    """P(X >= k) for Binomial(n, p)."""
    return sum(comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1))


dirs = sys.argv[1:]
if not dirs:
    latest = {}
    for d in glob.glob("D:/fabric-d2/results/x1_N*_*"):
        m = re.search(r"x1_N(\d+)_", os.path.basename(d))
        if m and os.path.isfile(os.path.join(d, "elections.csv")):
            n = int(m.group(1))
            if n not in latest or d > latest[n]:
                latest[n] = d
    dirs = [latest[k] for k in sorted(latest)]

for d in dirs:
    rows = list(csv.DictReader(open(os.path.join(d, "elections.csv"))))
    if not rows:
        continue
    N = int(rows[0]["N"]); M = int(rows[0]["m"])
    tg = sorted(int(t) for t in rows[0]["targets"].replace(",", ";").split(";") if t.strip())
    A = [x for x in rows if x["arm"] == "A_vanilla"]
    G = [x for x in rows if x["arm"] in ("B_oracle", "C_predictor")]

    print("=" * 68)
    print("N=%-3d m=%d targets=%s   vanilla elections=%d" % (N, M, tg, len(A)))
    print("=" * 68)

    winA = collections.Counter(int(x["leader_after"]) for x in A if x["leader_after"] != "0")
    winG = collections.Counter(int(x["leader_after"]) for x in G if x["leader_after"] != "0")

    print("  per-TARGET wins")
    for t in tg:
        print("    orderer%-3d  vanilla %2d   guarded %2d" % (t, winA[t], winG[t]))
    if M > 1:
        tot = sum(winA[t] for t in tg)
        if tot:
            hi = max(winA[t] for t in tg)
            # under symmetry each target is equally likely among the winning targets
            print("    symmetry check: %d target wins split %s; P(one target takes >=%d of %d"
                  " | uniform) = %.3f"
                  % (tot, [winA[t] for t in tg], hi, tot, binom_tail(hi, tot, 1.0 / M)))
        else:
            print("    symmetry check: no target wins in the vanilla arm")

    others = [i for i in range(1, N + 1) if i not in tg]
    ow = [winA[i] for i in others]
    print("  non-target wins (vanilla): total %d over %d nodes, min %d max %d, never-won %d"
          % (sum(ow), len(others), min(ow), max(ow), sum(1 for v in ow if v == 0)))
    top = sorted(((winA[i], i) for i in others), reverse=True)[:3]
    print("    most frequent: %s" % ", ".join("orderer%d=%d" % (i, c) for c, i in top))

    # how often was each target the paused leader -- an election it cannot win
    pl = collections.Counter(int(x["leader_before"]) for x in A if x["lb_was_target"] == "1")
    if pl:
        print("  target was the paused leader (cannot win that election): %s"
              % ", ".join("orderer%d=%d" % (k, v) for k, v in sorted(pl.items())))
    print()
