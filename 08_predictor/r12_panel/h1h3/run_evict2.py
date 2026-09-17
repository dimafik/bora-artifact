"""E-I (corrected): the advice is a step function, not a set of samples.

The first pass tested "was the leader in B_t at every logged advice line inside
the window", which makes a short window depend on whether a line happened to fall
in it -- hold 1 s suppressed more than hold 3 s, which is an artefact of the log
cadence and not a property of the policy. Here each advice line is taken to hold
until the next one, and the window is checked against that step function.

Two scopes are reported: the run the paper cites for the 159 demotions, and all
three phase-1 runs together.
"""
import os, re, glob, json
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
ROOT = os.environ.get("BORA_R13V3", r"D:\fabric-d2\results")
PAPER_RUN = "r13v3_N7_0815-202027"
RUNS = [PAPER_RUN, "r13v3_N7_0815-195411", "r13v3_N7_0815-193211"]
HOLDS = [0.0, 1.0, 3.0, 5.0, 10.0]
COOLDOWNS = [0.0, 15.0, 30.0, 60.0]
RES = "results_evict.json"


def read_fp(path):
    out = []
    for ln in open(path, encoding="utf8", errors="replace"):
        if ln.startswith("#"):
            continue
        m = re.match(r"([\d.]+) fp=\[([^\]]*)\] true=\[([^\]]*)\] merged=\[([^\]]*)\]", ln.strip())
        if m:
            out.append((float(m.group(1)),
                        {int(x) for x in re.findall(r"\d+", m.group(4))},
                        {int(x) for x in re.findall(r"\d+", m.group(3))}))
    return out


def read_demotes(path):
    out = []
    for ln in open(path, encoding="utf8", errors="replace"):
        m = re.match(r"([\d.]+) demote leader=(\d+) cause=(\w+)", ln.strip())
        if m:
            out.append((float(m.group(1)), int(m.group(2)), m.group(3)))
    return out


def first_ts(path):
    for ln in open(path, encoding="utf8", errors="replace"):
        p = ln.strip().split(",")
        if len(p) >= 2:
            try:
                return float(p[0])
            except ValueError:
                continue
    return None


def held_for(fp, t_rel, node, H):
    """With each advice line valid until the next, was `node` blacklisted for the
    whole window (t-H, t]?  H = 0 means "at this instant"."""
    if not fp:
        return False
    times = [t for t, _, _ in fp]
    lo = t_rel - H
    i = max(0, np.searchsorted(times, lo, side="right") - 1)
    j = np.searchsorted(times, t_rel, side="right")
    if j <= i:
        return node in fp[i][1]
    for k in range(i, j):
        if node not in fp[k][1]:
            return False
    return True


def collect(runs):
    rows, cells = [], 0
    for run in runs:
        for d in sorted(glob.glob(os.path.join(ROOT, run, "P1_D_*"))):
            fp_p = os.path.join(d, "fp.log")
            dm_p = os.path.join(d, "demote.log")
            ls_p = os.path.join(d, "leader_samples.csv")
            if not (os.path.exists(fp_p) and os.path.exists(ls_p)):
                continue
            t0 = first_ts(ls_p)
            if t0 is None:
                continue
            cells += 1
            fp = read_fp(fp_p)
            rate = int(re.search(r"_p(\d+)_", os.path.basename(d)).group(1))
            for t_abs, leader, cause in (read_demotes(dm_p) if os.path.exists(dm_p) else []):
                rel = t_abs - t0
                rows.append(dict(run=run, cell=os.path.basename(d), rate=rate, t=rel,
                                 leader=leader, cause=cause,
                                 hold={str(H): bool(held_for(fp, rel, leader, H)) for H in HOLDS}))
    return cells, rows


def policies(rows):
    out = {}
    for H in HOLDS:
        for C in COOLDOWNS:
            kept, last = [], {}
            for r in sorted(rows, key=lambda z: (z["run"], z["cell"], z["t"])):
                if not r["hold"][str(H)]:
                    continue
                key = (r["run"], r["cell"])
                if C > 0 and r["t"] - last.get(key, -1e9) < C:
                    continue
                last[key] = r["t"]
                kept.append(r)
            out["hold%g_cool%g" % (H, C)] = dict(
                kept=len(kept),
                fp=sum(1 for r in kept if r["cause"] == "FP"),
                tp=sum(1 for r in kept if r["cause"] == "TP"))
    return out


def main():
    res = {}
    for name, runs in (("paper_run", [PAPER_RUN]), ("all_three_runs", RUNS)):
        cells, rows = collect(runs)
        pol = policies(rows)
        res[name] = dict(cells=cells, recorded=len(rows), policies=pol,
                         by_rate={str(k): sum(1 for r in rows if r["rate"] == k)
                                  for k in sorted({r["rate"] for r in rows})})
        print("\n== %s: %d cells, %d recorded demotions (all false positives: %s)"
              % (name, cells, len(rows), all(r["cause"] == "FP" for r in rows)))
        print("%-10s" % "hold\\cool" + "".join("%10.0fs" % C for C in COOLDOWNS))
        for H in HOLDS:
            print("%-10.0fs" % H + "".join("%11d" % pol["hold%g_cool%g" % (H, C)]["kept"]
                                           for C in COOLDOWNS))
    json.dump(res, open(RES, "w"), indent=1)
    print("\nwritten", RES)


if __name__ == "__main__":
    main()
