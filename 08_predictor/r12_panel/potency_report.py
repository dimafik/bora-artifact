"""Both halves of the potency question in one report.

Table 1 -- leadership: does an evasive delay pattern still let the targeted
orderer acquire leadership, and does the guard stop it when detection works?

Table 2 -- throughput: does the pattern cost the ordering service anything?
The nodelay and healthy_white rows are what make this readable: nodelay is the
ceiling, healthy_white is the cost of the 500 ms base delay alone, and the
difference between healthy_white and the PGD rows is the part attributable to
autocorrelation rather than to latency.

Wilson intervals throughout.  The comparison that decides the question is 0%
against chance (14.3%), and at n=12 those give [0, 24%] and [5%, 45%] -- ranges
that overlap across most of their width.  Point estimates alone would invite
reading noise as a trend.
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

ORDER = ["nodelay", "healthy_white", "pgd_rho_0.0", "pgd_rho_0.3",
         "pgd_rho_0.6", "pgd_rho_0.8", "attack_class_ar1"]
LABEL = {"nodelay": "지연 없음 (상한)", "healthy_white": "healthy 500ms",
         "pgd_rho_0.0": "PGD rho=0", "pgd_rho_0.3": "PGD rho=0.3",
         "pgd_rho_0.6": "PGD rho=0.6", "pgd_rho_0.8": "PGD rho=0.8",
         "attack_class_ar1": "공격류 AR(1)"}
EVADED = {"pgd_rho_0.0": True, "pgd_rho_0.3": True, "pgd_rho_0.6": True,
          "pgd_rho_0.8": False}


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def rows_of(path, key="condition"):
    if not path or not os.path.exists(path):
        return {}
    return {r[key]: r for r in csv.DictReader(open(path, encoding="utf-8")) if r.get(key)}


def newest(pattern, inner):
    for d in sorted(glob.glob(os.path.join(POTENCY, pattern)),
                    key=os.path.getmtime, reverse=True):
        p = os.path.join(d, inner)
        if os.path.exists(p) and rows_of(p):
            return d, p
    return None, None


def main():
    scale = sys.argv[1] if len(sys.argv) > 1 else "m500"
    idx = json.load(open(os.path.join(POTENCY, "index.json"), encoding="utf-8"))
    meta = json.load(open(os.path.join(HERE, "pgd_sequences.json"), encoding="utf-8"))

    dbase, pbase = newest("run_%s_base_*" % scale, "summary.csv")
    dbora, pbora = newest("run_%s_bora_*" % scale, "summary.csv")
    dtput, ptput = newest("tput_%s_*" % scale, "tput.csv")
    base, bora, tput = rows_of(pbase), rows_of(pbora), rows_of(ptput)

    print("데이터 출처")
    for lbl, d in (("무가드", dbase), ("가드", dbora), ("처리량", dtput)):
        print("  %-6s %s" % (lbl, os.path.basename(d) if d else "(아직 없음)"))

    print("\n\n[표 1] 리더십 획득 — 표적 orderer3\n")
    h = ("조건", "자기상관", "탐지AUC", "회피", "무가드", "95% CI", "가드", "95% CI", "advisor")
    print("%-16s %8s %8s %5s %8s %-14s %8s %-14s %8s" % h)
    print("-" * 104)
    for c in ORDER:
        if c == "nodelay":
            continue
        tr = idx["tracks"].get("%s_%s.csv" % (scale, c), {})
        ac = tr.get("target_realised", {}).get("autocorr")
        auc = meta["conditions"].get(c, {}).get("auc")
        ev = EVADED.get(c)
        cells = []
        for src in (base, bora):
            r = src.get(c)
            if not r:
                cells += ["-", ""]
                continue
            k, n = int(r["wins"]), int(r["n"])
            lo, hi = wilson(k, n)
            cells += ["%d/%d" % (k, n), "[%.0f%%, %.0f%%]" % (100 * lo, 100 * hi)]
        rb = bora.get(c, {})
        adv = ("%s/%s" % (rb["advisor_ok"], rb["n"])
               if rb.get("advisor_ok") not in (None, "") else "-")
        print("%-16s %8s %8s %5s %8s %-14s %8s %-14s %8s"
              % (LABEL[c], "-" if ac is None else "%.3f" % ac,
                 "-" if auc is None else "%.3f" % auc,
                 "-" if ev is None else ("O" if ev else "X"),
                 cells[0], cells[1], cells[2], cells[3], adv))
    print("\n  균등 확률 1/7 = 14.3%.  회피 O = 탐지 AUC < 0.5.")
    bad = [c for c in ORDER if bora.get(c) and bora[c].get("advisor_ok")
           and bora[c]["advisor_ok"] != bora[c]["n"]]
    print("  advisor가 전 선출에서 7/7이 아니었던 조건:",
          bad or "없음 (fail-open 오염 없음)" if bora else "(가드 arm 미완)")

    print("\n\n[표 2] 처리량 — 커밋된 블록 (원장 기준)\n")
    print("%-16s %8s %9s %10s %12s %10s %10s"
          % ("조건", "자기상관", "블록", "블록/초", "vs healthy", "tx 성공", "tx/초"))
    print("-" * 84)
    ref = None
    for c in ORDER:
        r = tput.get(c)
        tr = idx["tracks"].get("%s_%s.csv" % (scale, c), {})
        ac = tr.get("target_realised", {}).get("autocorr")
        if not r or not r.get("blocks"):
            print("%-16s %8s %9s" % (LABEL[c], "-" if ac is None else "%.3f" % ac, "-"))
            continue
        bps = float(r["blocks_per_s"])
        if c == "healthy_white":
            ref = bps
        rel = "-" if (ref in (None, 0) or c in ("nodelay", "healthy_white")) \
            else "%+.1f%%" % (100 * (bps - ref) / ref)
        print("%-16s %8s %9s %10.4f %12s %10s %10s"
              % (LABEL[c], "-" if ac is None else "%.3f" % ac,
                 r["blocks"], bps, rel, r["tx_ok"], r["tx_per_s"]))
    print("\n  'vs healthy' = healthy 500ms 대비 변화. 즉 지연 자체가 아니라")
    print("  자기상관이 추가로 유발한 몫.")


if __name__ == "__main__":
    sys.exit(main())
