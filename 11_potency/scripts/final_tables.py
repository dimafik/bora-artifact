"""The two measurements that survived, with intervals.

Table 1 is a proportion over forty Bernoulli trials per cell, so it gets Wilson
intervals.  Table 3 is four repeated rate measurements per condition, so it gets
a mean and a t-interval, plus the position each repeat ran at -- the single-pass
version had every condition at a fixed position while the ledger grew underneath
it, and its one outlier (-12.3%) sat at position 3.
"""
import csv
import glob
import json
import math
import os
import statistics as st
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
POT = r"D:\fabric-d2\results\potency"
PANEL = r"D:\프랑스 업데이트\TNSE 스페셜이슈 논문\experiments\08_predictor\r12_panel"

ORDER = ["nodelay", "healthy_white", "pgd_rho_0.0", "pgd_rho_0.3",
         "pgd_rho_0.6", "pgd_rho_0.8", "attack_class_ar1"]
LABEL = {"nodelay": "지연 없음", "healthy_white": "healthy 500ms",
         "pgd_rho_0.0": "PGD rho=0", "pgd_rho_0.3": "PGD rho=0.3",
         "pgd_rho_0.6": "PGD rho=0.6", "pgd_rho_0.8": "PGD rho=0.8",
         "attack_class_ar1": "공격류 AR(1)"}
EVADED = {"pgd_rho_0.0": "O", "pgd_rho_0.3": "O", "pgd_rho_0.6": "O", "pgd_rho_0.8": "X"}
T95 = {2: 12.706, 3: 4.303, 4: 3.182, 5: 2.776}     # two-sided, df = n-1


def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def newest(pat, inner):
    for d in sorted(glob.glob(os.path.join(POT, pat)), key=os.path.getmtime, reverse=True):
        p = os.path.join(d, inner)
        if os.path.exists(p) and len(open(p, encoding="utf-8").read().splitlines()) > 1:
            return d, p
    return None, None


idx = json.load(open(os.path.join(POT, "index.json"), encoding="utf-8"))
meta = json.load(open(os.path.join(PANEL, "pgd_sequences.json"), encoding="utf-8"))

# ---------------------------------------------------------------- table 1
db, pb = newest("run_m500_base_*", "summary.csv")
dg, pg = newest("run_m500_bora_*", "summary.csv")
base = {r["condition"]: r for r in csv.DictReader(open(pb, encoding="utf-8"))}
bora = {r["condition"]: r for r in csv.DictReader(open(pg, encoding="utf-8"))}

print("[표 1] 리더십 획득 — 표적 orderer3, 조건당 40선출, m500")
print("        무가드 %s / 운영자지정 가드 %s\n" % (os.path.basename(db), os.path.basename(dg)))
print("%-16s %8s %8s %4s | %7s %-14s | %7s %-14s | %s"
      % ("조건", "자기상관", "탐지AUC", "회피", "무가드", "95% CI", "가드", "95% CI", "advisor"))
print("-" * 108)
for c in ORDER:
    if c == "nodelay":
        continue
    tr = idx["tracks"].get("m500_%s.csv" % c, {})
    ac = tr.get("target_realised", {}).get("autocorr")
    auc = meta["conditions"].get(c, {}).get("auc")
    row = []
    for src in (base, bora):
        r = src[c]
        k, n = int(r["wins"]), int(r["n"])
        lo, hi = wilson(k, n)
        row += ["%d/%d" % (k, n), "[%.0f%%, %.0f%%]" % (100 * lo, 100 * hi)]
    print("%-16s %8s %8s %4s | %7s %-14s | %7s %-14s | %s/%s"
          % (LABEL[c], "%.3f" % ac, "-" if auc is None else "%.3f" % auc,
             EVADED.get(c, "-"), row[0], row[1], row[2], row[3],
             bora[c]["advisor_ok"], bora[c]["n"]))
print("\n  균등 확률 1/7 = 14.3%.  회피 O = 백박스 탐지 AUC < 0.5.")
print("  가드 열은 블랙리스트를 [3]으로 지정한 조건이라 배제 메커니즘의 성질이지 탐지 성능이 아님.")

# ---------------------------------------------------------------- table 3
dt, pt = newest("tputrep_*", "tput.csv")
rows = list(csv.DictReader(open(pt, encoding="utf-8")))
by = {}
for r in rows:
    by.setdefault(r["condition"], []).append(r)

print("\n\n[표 3] 처리량 — 커밋 블록/초, 조건당 4회 반복, 순서 회전, m500")
print("        %s\n" % os.path.basename(dt))
print("%-16s %8s %5s %9s %9s %-16s %10s %s"
      % ("조건", "자기상관", "n", "평균", "표준편차", "95% CI", "vs healthy", "실행 위치"))
print("-" * 100)
ref = st.mean([float(r["blocks_per_s"]) for r in by["healthy_white"]])
for c in ORDER:
    v = [float(r["blocks_per_s"]) for r in by[c]]
    pos = ",".join(r["position"] for r in by[c])
    m, s, n = st.mean(v), (st.stdev(v) if len(v) > 1 else 0.0), len(v)
    h = T95.get(n, 3.182) * s / math.sqrt(n) if n > 1 else 0.0
    tr = idx["tracks"].get("m500_%s.csv" % c, {})
    ac = tr.get("target_realised", {}).get("autocorr")
    rel = "-" if c in ("nodelay", "healthy_white") else "%+.1f%%" % (100 * (m - ref) / ref)
    print("%-16s %8s %5d %9.4f %9.4f [%.4f, %.4f] %10s %s"
          % (LABEL[c], "-" if ac is None else "%.3f" % ac, n, m, s, m - h, m + h, rel, pos))

allv = [float(r["blocks_per_s"]) for c in ORDER if c not in ("nodelay",) for r in by[c]]
atk = [float(r["blocks_per_s"]) for c in ORDER if c not in ("nodelay", "healthy_white") for r in by[c]]
print("\n  지연 없음 대비 healthy 500ms: %.1f%%" % (100 * (ref / st.mean([float(r["blocks_per_s"]) for r in by["nodelay"]]) - 1)))
print("  500ms 조건 20개 전체: 평균 %.4f, 표준편차 %.4f (변동계수 %.1f%%)"
      % (st.mean(allv), st.stdev(allv), 100 * st.stdev(allv) / st.mean(allv)))
print("  자기상관 조건 20개만: 평균 %.4f, 표준편차 %.4f" % (st.mean(atk), st.stdev(atk)))
tx = [int(r["tx_ok"]) for r in rows]
tried = [int(r["tx_tried"]) for r in rows]
print("  트랜잭션 성공 %d/%d (%.2f%%)" % (sum(tx), sum(tried), 100 * sum(tx) / sum(tried)))
