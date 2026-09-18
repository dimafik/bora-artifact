"""Combine the two phase-4 runs into one 36-cell table.

The first run covered seeds 1-4 in full and stopped inside seed 5 when the
injector gate fired; the second resumed at seed 5. Seeds 1-4 therefore come from
the first run and seeds 5-6 from the second, which is 36 cells with nothing
counted twice. Both ran the same v5 binary and the same harness; the only
difference is how long the gate waits for the injector's first file.
"""
import csv, os, collections

RAW = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "..", "..", "02_results_raw")
RUNS = [(os.path.join(RAW, "r13p4_N7_0917-163626"), (1, 2, 3, 4)),
        (os.path.join(RAW, "r13p4_N7_0917-223327"), (5, 6))]
ARMS = ("A", "D", "P")
NAME = {"A": "Active-Leader Rule (as shipped)", "D": "evict on every flag",
        "P": "evict after 10 s hold, one a minute"}


def rows():
    for path, seeds in RUNS:
        p = os.path.join(path, "cells.csv")
        if not os.path.exists(p):
            continue
        for r in csv.DictReader(open(p)):
            if int(r["seed"]) in seeds and r["demotions"] not in ("-", ""):
                r["run"] = os.path.basename(path)
                yield r


def main():
    rs = list(rows())
    print("cells: %d" % len(rs))
    agg = collections.defaultdict(lambda: collections.defaultdict(float))
    for r in rs:
        for key in (r["arm"], "%s/%s" % (r["arm"], r["rate"])):
            a = agg[key]
            a["n"] += 1
            a["tp"] += int(r["demote_TP"])
            a["fp"] += int(r["demote_FP"])
            a["tenure"] += int(r["target_tenure_s"])
            a["leaderless"] += int(r["leaderless_s"])
            a["settle"] += float(r["settle_s"])
            a["safety"] += int(r["safety_viol"]) if r["safety_viol"].isdigit() else 0
            a["held"] += 1 if int(r["target_leader_at_end"] or 0) == 3 else 0

    print("\n=== by arm (36 cells, six seeds) ===")
    print("%-38s %5s %5s %5s %9s %11s %8s %8s" %
          ("policy", "cells", "TP", "FP", "tenure_s", "leaderless", "settle", "safety"))
    for arm in ARMS:
        a = agg[arm]
        if not a["n"]:
            continue
        print("%-38s %5d %5d %5d %9.1f %11.1f %8.0f %8d" %
              (NAME[arm], a["n"], a["tp"], a["fp"], a["tenure"] / a["n"],
               a["leaderless"] / a["n"], a["settle"] / a["n"], int(a["safety"])))

    print("\n=== by injected false-positive rate ===")
    print("%-6s %-6s %5s %5s %5s %9s %11s" % ("arm", "rate", "cells", "TP", "FP", "tenure_s", "leaderless"))
    for arm in ARMS:
        for rate in ("10", "20"):
            a = agg["%s/%s" % (arm, rate)]
            if not a["n"]:
                continue
            print("%-6s %-6s %5d %5d %5d %9.1f %11.1f" %
                  (arm, rate + "%", a["n"], a["tp"], a["fp"], a["tenure"] / a["n"], a["leaderless"] / a["n"]))

    print("\n=== per cell ===")
    print("%-4s %-5s %-5s %4s %4s %8s %11s %5s" % ("arm", "rate", "seed", "TP", "FP", "tenure", "leaderless", "end"))
    for r in sorted(rs, key=lambda z: (z["arm"], int(z["rate"]), int(z["seed"]))):
        print("%-4s %-5s %-5s %4s %4s %8s %11s %5s" %
              (r["arm"], r["rate"], r["seed"], r["demote_TP"], r["demote_FP"],
               r["target_tenure_s"], r["leaderless_s"], r["target_leader_at_end"]))


if __name__ == "__main__":
    main()
