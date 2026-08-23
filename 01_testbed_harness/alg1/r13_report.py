#!/usr/bin/env python3
"""Aggregate an R1-3 v2 run into the table the paper needs.

Reports, per arm and false-positive rate:
  elections            forced elections (identical cadence in every arm)
  leader_changes       raw churn seen in the raft logs
  demotions TP/FP      leader moves the AUTHORITY interface caused, by cause
  liveness_fail        forced elections with no leader within 25 s
  mean_ttl_s           time to a new leader
  delivered            elections where the orderer provably held the advice
  safety               invariant violations

Usage: r13_report.py <run_dir>
"""
import csv, io, os, sys, collections

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

run = sys.argv[1]
rows = list(csv.DictReader(open(os.path.join(run, "cells.csv"))))
if not rows:
    raise SystemExit("no cells")

I = lambda r, k: int(float(r[k]))
ARMS = {"A": "vanilla", "C": "BORA", "D": "authority"}
rates = sorted({int(r["rate"]) for r in rows})

agg = collections.defaultdict(lambda: collections.defaultdict(float))
for r in rows:
    k = (r["arm"], int(r["rate"]))
    for f in ("elections", "elec_with_fp", "leader_changes", "demotions",
              "demote_TP", "demote_FP", "liveness_fail", "advice_seen", "safety_viol"):
        agg[k][f] += I(r, f)
    try:
        agg[k]["ttl_sum"] += float(r["mean_ttl_s"]); agg[k]["ttl_n"] += 1
    except ValueError:
        pass

print("%-11s %-4s %6s %8s %8s %6s %6s %9s %8s %9s %6s" % (
    "arm", "p%", "elec", "changes", "demote", "TP", "FP", "livefail", "ttl_s",
    "delivered", "safety"))
for a in "ACD":
    for p in rates:
        v = agg[(a, p)]
        if not v:
            continue
        ttl = v["ttl_sum"] / v["ttl_n"] if v["ttl_n"] else float("nan")
        print("%-11s %-4d %6d %8d %8d %6d %6d %9d %8.2f %9d %6d" % (
            ARMS[a], p, v["elections"], v["leader_changes"], v["demotions"],
            v["demote_TP"], v["demote_FP"], v["liveness_fail"], ttl,
            v["advice_seen"], v["safety_viol"]))
    print()

tot = collections.defaultdict(float)
for r in rows:
    for f in ("elections", "liveness_fail", "safety_viol"):
        tot[f] += I(r, f)
print("cells=%d  elections=%d  liveness_fail=%d  safety_violations=%d"
      % (len(rows), tot["elections"], tot["liveness_fail"], tot["safety_viol"]))

# the claim the paper would make, stated as the numbers that support it
adv = sum(I(r, "demotions") for r in rows if r["arm"] == "D")
non = sum(I(r, "demotions") for r in rows if r["arm"] in ("A", "C"))
seen = sum(I(r, "advice_seen") for r in rows if r["arm"] == "C")
print("authority-arm leader moves caused by the learner: %d" % adv)
print("advisory-arm  leader moves caused by the learner: %d" % non)
print("arm C elections with advice provably on the orderer: %d" % seen)
