#!/usr/bin/env python3
"""Check Algorithm 1 substep (c) against every advice cycle the advisor logged.

Algorithm 1 emits

    B_t <- top(p_t, H_t, max(f - r - 1, 0))

so the contract at emission is |B_t| <= max(f - r - 1, 0), which implies the
|B_t| < f that BORA.tla's BoundedCap and the safety proof use. r is the
Raft-observed unhealthy count, so the cap contracts as the cluster degrades and
reaches zero before r reaches f: the advisor stands down rather than compounding
a real failure.

The advisor writes r and the applied cap on every cycle, which makes that
contract checkable line by line rather than at the summary level. This script
does exactly that and reports any line where either the cap was computed
differently or the emitted blacklist exceeded it.

    python3 02_results_raw/cap_audit/cap_audit.py

Scope: the log this reads is the B-20 sweep's advisor, which carries the
zero-parameter mean-RTT detector in the scoring slot. Everything downstream of
scoring -- the r derivation, the cap, the advice payload -- is copied unchanged
from predictor_daemon_n.py, so the cap path under test is the shipped one. The
older mldetect_* daemon logs predate the per-cycle r/cap audit trail and carry
no cap field, so they cannot be checked this way.
"""
import collections
import gzip
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
LOG = os.path.join(HERE, os.pardir, "b20_sweep_20260903-162221",
                   "predictor_daemon_meanrtt.log.gz")

START = re.compile(r"daemon start .*N=(\d+) f=(\d+)")
CYCLE = re.compile(r"Bt=(\[[^\]]*\]|\S+)\s+r=(\d+)\s+cap=(-?\d+)")


def main(path):
    if not os.path.exists(path):
        sys.exit("log not found: %s" % path)
    nf = None
    checked = bad_cap = bad_size = 0
    per_n = collections.Counter()
    worst = collections.Counter()          # highest r seen per N
    clamped = collections.Counter()        # cycles where r >= f, so f-r-1 < 0
    violations = []

    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as fh:
        for line in fh:
            m = START.search(line)
            if m:
                nf = (int(m.group(1)), int(m.group(2)))
                continue
            m = CYCLE.search(line)
            if not m or nf is None:
                continue
            n, f = nf
            bt = re.findall(r"\d+", m.group(1))
            r, cap = int(m.group(2)), int(m.group(3))
            expected = max(0, f - r - 1)

            checked += 1
            per_n[n] += 1
            worst[n] = max(worst[n], r)
            if r >= f:
                clamped[n] += 1
            if cap != expected:
                bad_cap += 1
                violations.append("cap: N=%d f=%d r=%d logged=%d expected=%d"
                                  % (n, f, r, cap, expected))
            if len(bt) > cap:
                bad_size += 1
                violations.append("size: N=%d f=%d r=%d cap=%d |B_t|=%d"
                                  % (n, f, r, cap, len(bt)))

    print("advice cycles checked: %d" % checked)
    print()
    print("%-6s %-12s %-20s %s"
          % ("N", "cycles", "highest r observed", "cycles with r >= f"))
    for n in sorted(per_n):
        print("%-6d %-12d %-20d %d" % (n, per_n[n], worst[n], clamped[n]))
    print()
    print("cycles where f - r - 1 is negative, so the max(.,0) clamp is what")
    print("keeps substep (c) defined: %d" % sum(clamped.values()))
    print()
    print("cap != max(0, f - r - 1) : %d" % bad_cap)
    print("|B_t| > cap              : %d" % bad_size)
    for v in violations[:20]:
        print("   ", v)
    if len(violations) > 20:
        print("    ... and %d more" % (len(violations) - 20))
    return 1 if violations else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else LOG))
