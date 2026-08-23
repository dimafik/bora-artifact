#!/usr/bin/env python3
"""Metrics for the R1-3 interface experiment.

Two things the first draft of the shell driver got wrong, both of which would
have produced a wrong answer rather than an error:

1. LEADER CHANGES WERE COUNTED N TIMES.  Every orderer logs its own view of a
   leader change, so collecting "Raft leader changed" from all N containers and
   running `sort -u` does not deduplicate -- the timestamps differ by
   milliseconds.  At N=7 that inflates the count sevenfold, and since it
   inflates every arm it would have looked plausible.  Here a change is keyed by
   (old, new, 2-second bucket) and counted once.

2. "FALSE POSITIVE LANDED ON THE LEADER" WAS ONLY MEASURED IN ARM D, because it
   was read out of the authority actuator's own log.  That is the arm where it
   causes a demotion; it is exactly as important in arm C, where the claim is
   that it causes NOTHING.  Here it is derived for every arm identically, from
   the schedule and the leader timeline.

Usage:  r13_metrics.py <cell_dir> <n> <target> <dur>
Prints one CSV row.
"""
import os, re, sys
from datetime import datetime

BUCKET = 2.0     # seconds; same election seen by several nodes collapses to one


def parse_ts(s):
    s = s.strip().replace("Z", "+00:00")
    s = re.sub(r"(\.\d{6})\d+", r"\1", s)      # docker prints nanoseconds
    return datetime.fromisoformat(s).timestamp()


def load_changes(path):
    """[(t, old, new)] deduplicated across the N per-node views."""
    seen, out = set(), []
    if not os.path.exists(path):
        return out
    for line in open(path):
        p = line.split()
        if len(p) < 3:
            continue
        try:
            t = parse_ts(p[0])
        except Exception:
            continue
        old, new = p[1], p[2]
        key = (old, new, round(t / BUCKET))
        if key in seen:
            continue
        seen.add(key)
        out.append((t, old, new))
    return sorted(out)


def load_schedule(path):
    out = []
    if os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if not line:
                continue
            t, node = line.split(",")
            out.append((float(t), int(node)))
    return out


def main():
    cdir, n, target, dur = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]), float(sys.argv[4])
    ch = load_changes(os.path.join(cdir, "leader_changes.txt"))
    sched = load_schedule(os.path.join(cdir, "schedule.csv"))

    # The leader at the START of the window, captured from the ops endpoint.
    # Leader changes alone are not enough: a cell with no change has no timeline
    # at all, and every "did the false positive name the incumbent?" question
    # then answers no by default rather than by measurement.
    l0 = 0
    p0 = os.path.join(cdir, "leader0.txt")
    if os.path.exists(p0):
        try:
            l0 = int(open(p0).read().strip() or 0)
        except ValueError:
            l0 = 0

    t0 = ch[0][0] if ch else 0.0
    timeline = [(0.0, l0)] + [(t - t0, int(new)) for t, _, new in ch]

    def leader_at(rel):
        cur = 0
        for ts, node in timeline:
            if ts <= rel:
                cur = node
            else:
                break
        return cur

    fp_on_leader = sum(1 for rel, node in sched if leader_at(rel) == node)

    # seconds the degraded target held leadership
    target_s = 0.0
    for i, (ts, node) in enumerate(timeline):
        end = timeline[i + 1][0] if i + 1 < len(timeline) else dur
        if node == target:
            target_s += max(0.0, min(end, dur) - ts)

    print("%d,%d,%d,%.1f" % (len(ch), len(sched), fp_on_leader, target_s))


if __name__ == "__main__":
    main()
