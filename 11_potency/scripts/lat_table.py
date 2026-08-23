"""Table 4: commit-latency tails per condition.

Throughput and leadership are means over minutes; a bursty delay is expected to
show up in the tail instead, so this is the metric where the attack had its best
chance of appearing.  Percentiles are reported per repeat and then averaged, with
the spread between repeats shown, because with two repeats an average alone
would hide whether the conditions differ by more than the runs do.
"""
import csv
import glob
import json
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

d = sorted(glob.glob(os.path.join(POT, "lat_m500_*")), key=os.path.getmtime)[-1]
rows = list(csv.DictReader(open(os.path.join(d, "latency.csv"), encoding="utf-8")))
by = {}
for r in rows:
    by.setdefault(r["condition"], []).append(r)

idx = json.load(open(os.path.join(POT, "index.json"), encoding="utf-8"))
meta = json.load(open(os.path.join(PANEL, "pgd_sequences.json"), encoding="utf-8"))

print("[표 4] 커밋 지연 (ms) — --waitForEvent 기준 end-to-end, 2회 반복, 순서 회전")
print("        %s\n" % os.path.basename(d))
print("%-16s %8s %8s %5s %5s %14s %14s %14s %10s"
      % ("조건", "자기상관", "탐지AUC", "n", "실패", "p50 (반복별)", "p95 (반복별)",
         "p99 (반복별)", "vs healthy"))
print("-" * 112)


def pair(c, key):
    v = [int(r[key]) for r in by[c]]
    return v, st.mean(v)


ref99 = pair("healthy_white", "p99")[1]
for c in ORDER:
    tr = idx["tracks"].get("m500_%s.csv" % c, {})
    ac = tr.get("target_realised", {}).get("autocorr")
    auc = meta["conditions"].get(c, {}).get("auc")
    n = sum(int(r["n"]) for r in by[c])
    f = sum(int(r["fail"]) for r in by[c])
    p50, m50 = pair(c, "p50")
    p95, m95 = pair(c, "p95")
    p99, m99 = pair(c, "p99")
    rel = "-" if c in ("nodelay", "healthy_white") else "%+.1f%%" % (100 * (m99 - ref99) / ref99)
    print("%-16s %8s %8s %5d %5d %14s %14s %14s %10s"
          % (LABEL[c], "-" if ac is None else "%.3f" % ac,
             "-" if auc is None else "%.3f" % auc, n, f,
             "%d (%d,%d)" % (m50, p50[0], p50[1]),
             "%d (%d,%d)" % (m95, p95[0], p95[1]),
             "%d (%d,%d)" % (m99, p99[0], p99[1]), rel))

nd = pair("nodelay", "p50")[1]
hw = pair("healthy_white", "p50")[1]
print("\n  지연 없음 -> healthy 500ms:  p50 %.0f -> %.0f ms (%.1f배)" % (nd, hw, hw / nd))
atk99 = [int(r["p99"]) for c in ORDER if c not in ("nodelay", "healthy_white") for r in by[c]]
all99 = [int(r["p99"]) for c in ORDER if c != "nodelay" for r in by[c]]
print("  500ms 조건 p99 전체(12측정): %.0f ~ %.0f ms, 표준편차 %.0f (변동계수 %.1f%%)"
      % (min(all99), max(all99), st.stdev(all99), 100 * st.stdev(all99) / st.mean(all99)))
print("  자기상관 최저(0.026)와 최고(0.886)의 p99 차: %.0f ms"
      % (pair("attack_class_ar1", "p99")[1] - ref99))
print("  타임아웃 실패: %d건 (waitForEventTimeout 60s)" % sum(int(r["fail"]) for r in rows))
