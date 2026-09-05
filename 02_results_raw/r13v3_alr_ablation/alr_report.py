#!/usr/bin/env python3
"""Recompute the Active-Leader-Rule ablation from the shipped cells.csv.

Phase 1 of the r13v3 campaign asks what the Active-Leader Rule is worth. Three
arms run the same 36 cells: A is vanilla Raft, C is BORA, and D is BORA with
only the ALR removed, so the predictor may demote a sitting leader. Everything
else -- the cap, the guards, the fail-open counter -- is identical across C
and D, which is what makes it an ablation of one rule rather than a comparison
of two systems.

Only r13v3_N7_0815-202027 carries the campaign. The two sibling directories are
partial bring-ups and are excluded by name here; see README.md.

    python3 02_results_raw/r13v3_alr_ablation/alr_report.py
"""
import collections
import csv
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CAMPAIGN = os.path.join(HERE, os.pardir, "r13v3_N7_0815-202027", "cells.csv")
PARTIAL = ("r13v3_N7_0815-193211", "r13v3_N7_0815-195411")
RATES = ("0", "5", "10", "20")
ARMS = (("A", "vanilla Raft"), ("C", "BORA"), ("D", "BORA minus ALR"))


def main(path):
    if not os.path.exists(path):
        sys.exit("cells.csv not found: %s" % path)
    rows = [r for r in csv.DictReader(open(path)) if r["phase"] == "P1"]
    tot = collections.defaultdict(lambda: collections.defaultdict(float))
    rate = collections.defaultdict(lambda: collections.defaultdict(float))
    for r in rows:
        a = r["arm"]
        for k in ("elections", "demotions", "demote_TP", "demote_FP",
                  "leader_changes", "safety_viol", "advice_seen", "liveness_fail"):
            tot[a][k] += int(r[k] or 0)
        tot[a]["leaderless_s"] += float(r["leaderless_s"] or 0)
        rate[(a, r["rate"])]["dem"] += int(r["demotions"] or 0)
        rate[(a, r["rate"])]["ll"] += float(r["leaderless_s"] or 0)

    print("campaign : %s" % os.path.basename(os.path.dirname(path)))
    print("P1 cells : %d   (excluded partials: %s)" % (len(rows), ", ".join(PARTIAL)))
    print()
    print("%-4s %-16s %6s %6s %5s %5s %8s %11s %6s"
          % ("arm", "", "elec", "demote", "TP", "FP", "chg", "leaderless", "safety"))
    for a, name in ARMS:
        t = tot[a]
        print("%-4s %-16s %6d %6d %5d %5d %8d %10.0fs %6d"
              % (a, name, t["elections"], t["demotions"], t["demote_TP"],
                 t["demote_FP"], t["leader_changes"], t["leaderless_s"],
                 t["safety_viol"]))
    print()
    print("demotions by injected false-positive rate")
    for a, name in ARMS:
        print("  %-4s %s" % (a, "  ".join("p=%s%%: %d" % (p, rate[(a, p)]["dem"])
                                          for p in RATES)))
    print()
    print("leaderless seconds, and the ratio against vanilla Raft")
    for a, name in ARMS:
        cells = []
        for p in RATES:
            ll = rate[(a, p)]["ll"]
            base = rate[("A", p)]["ll"]
            cells.append("p=%s%%: %.0fs (%.2fx)" % (p, ll, ll / base if base else 0))
        print("  %-4s %s" % (a, "  ".join(cells)))
    print()
    print("advice actually delivered to an orderer: C %d elections, D %d"
          % (tot["C"]["advice_seen"], tot["D"]["advice_seen"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else CAMPAIGN))
