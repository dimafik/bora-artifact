"""Tabulate the potency campaigns: does an evasive delay pattern still do harm?

Reads whatever run directories exist under results/potency and joins them to the
detector's own numbers, so evasion and effect sit in one table.

Wilson intervals rather than bare proportions: twelve elections per condition is
a small sample, and 1/12 against 2/12 is not a difference -- printing point
estimates alone invites reading noise as a trend.  The interval is the honest
width to argue from.
"""
import csv
import glob
import json
import math
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

POTENCY = r"D:\fabric-d2\results\potency"
HERE = os.path.dirname(os.path.abspath(__file__))

ORDER = ["healthy_white", "pgd_rho_0.0", "pgd_rho_0.3",
         "pgd_rho_0.6", "pgd_rho_0.8", "attack_class_ar1"]
LABEL = {"healthy_white": "healthy (대조)", "pgd_rho_0.0": "PGD rho=0",
         "pgd_rho_0.3": "PGD rho=0.3", "pgd_rho_0.6": "PGD rho=0.6",
         "pgd_rho_0.8": "PGD rho=0.8", "attack_class_ar1": "공격류 AR(1)"}


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def read_run(d):
    f = os.path.join(d, "summary.csv")
    if not os.path.exists(f):
        return {}
    out = {}
    for r in csv.DictReader(open(f, encoding="utf-8")):
        out[r["condition"]] = r
    return out


def latest(scale, arm):
    ds = sorted(glob.glob(os.path.join(POTENCY, "run_%s_%s_*" % (scale, arm))),
                key=os.path.getmtime, reverse=True)
    for d in ds:
        if read_run(d):
            return d
    return None


def main():
    scale = sys.argv[1] if len(sys.argv) > 1 else "m500"
    idx = json.load(open(os.path.join(POTENCY, "index.json"), encoding="utf-8"))
    meta = json.load(open(os.path.join(HERE, "pgd_sequences.json"), encoding="utf-8"))

    dirs = {a: latest(scale, a) for a in ("base", "bora")}
    runs = {a: (read_run(d) if d else {}) for a, d in dirs.items()}
    for a, d in dirs.items():
        print("%-5s : %s" % (a, os.path.basename(d) if d else "(아직 없음)"))
    print()

    hdr = ("조건", "자기상관", "탐지AUC", "무가드", "95% CI", "가드", "95% CI", "live", "advisor")
    print("%-15s %8s %8s %8s %-14s %8s %-14s %7s %8s" % hdr)
    print("-" * 104)

    for c in ORDER:
        track = idx["tracks"].get("%s_%s.csv" % (scale, c), {})
        ac = track.get("target_realised", {}).get("autocorr")
        auc = meta["conditions"].get(c, {}).get("auc")

        cells = []
        for arm in ("base", "bora"):
            r = runs[arm].get(c)
            if not r:
                cells += ["-", ""]
                continue
            k, n = int(r["wins"]), int(r["n"])
            lo, hi = wilson(k, n)
            cells += ["%d/%d" % (k, n), "[%.0f%%, %.0f%%]" % (100 * lo, 100 * hi)]

        rb = runs["bora"].get(c) or runs["base"].get(c) or {}
        live = "%s/%s" % (rb.get("liveness", "-"), rb.get("n", "-"))
        adv = runs["bora"].get(c, {}).get("advisor_ok")
        adv = "-" if adv is None else "%s/%s" % (adv, runs["bora"][c]["n"])

        print("%-15s %8s %8s %8s %-14s %8s %-14s %7s %8s"
              % (LABEL[c],
                 "-" if ac is None else "%.3f" % ac,
                 "-" if auc is None else "%.3f" % auc,
                 cells[0], cells[1], cells[2], cells[3], live, adv))

    print("\n주: 균등 확률은 1/7 = 14.3% (12회 중 1.7회). 탐지 AUC < 0.5 = 회피 성공.")
    if runs["bora"]:
        bad = [c for c in ORDER
               if (runs["bora"].get(c) and runs["bora"][c].get("advisor_ok")
                   and runs["bora"][c]["advisor_ok"] != runs["bora"][c]["n"])]
        print("advisor가 전 선출에서 7/7이 아니었던 조건:", bad or "없음 (fail-open 오염 없음)")


if __name__ == "__main__":
    sys.exit(main())
