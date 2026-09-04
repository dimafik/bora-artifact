# Aggregate the B-20 sweep into the form the paper already reports for the
# published campaign, so the two can be set side by side without the reader
# doing arithmetic: per-arm totals, a Wilson upper bound, and the one-sided
# Fisher exact test against the unguarded arm.
#
# Arm C in this sweep carries the zero-parameter mean-RTT threshold rather than
# the Transformer. Arms A and B are unchanged, which is what makes the
# comparison controlled: the same run supplies its own baseline.
import glob
import math
import os
import re
import sys
from collections import defaultdict

sys.stdout.reconfigure(encoding="utf-8")

PUBLISHED = {"A_vanilla": (21, 240), "B_oracle": (0, 240), "C_predictor": (0, 240)}


def wilson_upper(k, n, z=1.959963985):
    """Upper end of the 95% Wilson score interval for k successes in n."""
    if n == 0:
        return float("nan")
    p = k / n
    d = 1 + z * z / n
    centre = p + z * z / (2 * n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (centre + half) / d


def fisher_one_sided(a, b, c, d):
    """P(as extreme or more) for the 2x2 [[a,b],[c,d]], testing that the
    guarded arm wins less often. Rows are arms, columns are win / no-win."""
    n = a + b + c + d
    total = 0.0
    for x in range(0, min(a + b, a + c) + 1):
        if x > a:
            continue
        p = (math.comb(a + b, x) * math.comb(c + d, a + c - x)) / math.comb(n, a + c)
        total += p
    return min(1.0, total)


def collect(sweep_dir):
    per_run = []
    for f in sorted(glob.glob(os.path.join(sweep_dir, "x1_N*_run*.log"))):
        arms = defaultdict(lambda: [0, 0, 0])   # wins, elections, live
        for line in open(f, encoding="utf-8", errors="replace"):
            m = re.search(r"(A_vanilla|B_oracle|C_predictor) s\d+: target (\d+)/(\d+)"
                          r"\s+live (\d+)/(\d+)", line)
            if m:
                a = arms[m.group(1)]
                a[0] += int(m.group(2)); a[1] += int(m.group(3)); a[2] += int(m.group(4))
        if arms:
            n = re.search(r"x1_N(\d+)_run(\d+)", os.path.basename(f))
            per_run.append((int(n.group(1)), int(n.group(2)), dict(arms)))
    return per_run


def main(sweep_dir):
    per_run = collect(sweep_dir)
    if not per_run:
        print("결과 없음:", sweep_dir); return
    print("=== 실행별 ===")
    print("%-6s %-6s %s" % ("N", "run", "  ".join("%-22s" % k for k in
          ("A_vanilla", "B_oracle", "C_predictor(0-param)"))))
    tot = defaultdict(lambda: [0, 0, 0])
    for N, run, arms in per_run:
        cells = []
        for k in ("A_vanilla", "B_oracle", "C_predictor"):
            w, e, lv = arms.get(k, (0, 0, 0))
            cells.append("%-22s" % ("%d/%d (live %d)" % (w, e, lv)))
            t = tot[k]; t[0] += w; t[1] += e; t[2] += lv
        print("%-6d %-6d %s" % (N, run, "  ".join(cells)))

    print()
    print("=== 합계 ===")
    print("%-24s %10s %12s %14s" % ("arm", "target wins", "95% Wilson", "live"))
    for k in ("A_vanilla", "B_oracle", "C_predictor"):
        w, e, lv = tot[k]
        if e == 0:
            continue
        print("%-24s %10s %12s %14s"
              % (k + (" (0-param)" if k == "C_predictor" else ""),
                 "%d/%d" % (w, e), "[0, %.1f%%]" % (100 * wilson_upper(w, e)),
                 "%d/%d" % (lv, e)))

    a_w, a_e, _ = tot["A_vanilla"]
    c_w, c_e, _ = tot["C_predictor"]
    if a_e and c_e:
        p = fisher_one_sided(c_w, c_e - c_w, a_w, a_e - a_w)
        print()
        print("Fisher exact (one-sided, guarded vs unguarded): p = %.2e" % p)

    print()
    print("=== 발표된 캠페인(트랜스포머)과 대조 ===")
    print("%-24s %14s %14s" % ("arm", "published", "this sweep"))
    for k in ("A_vanilla", "B_oracle", "C_predictor"):
        pw, pe = PUBLISHED[k]
        w, e, _ = tot[k]
        print("%-24s %14s %14s" % (k, "%d/%d" % (pw, pe), "%d/%d" % (w, e) if e else "-"))


if __name__ == "__main__":
    # default: the shipped sweep, resolved relative to this file
    here = os.path.dirname(os.path.abspath(__file__))
    d = sys.argv[1] if len(sys.argv) > 1 else sorted(glob.glob(os.path.join(
        here, "..", "..", "02_results_raw", "b20_sweep_*")))[-1]
    print("sweep:", d)
    print()
    main(d)
