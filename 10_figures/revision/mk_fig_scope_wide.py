# The evidence base -- full-width, four panels.
#
# Grandeur here is the number of AXES the work spans, not a bigger headline:
# four months, six cluster sizes, several adversary classes, a mechanised core.
# Every count is read out of a results file at run time, and panel (b) counts
# only elections the manuscript cites as exclusion evidence -- the eviction
# ablation, the unreported threshold-swap arm and the two runs excluded by name
# are left out, and the caption says so.
#
# Deliberately NOT drawn: a bar chart of proof obligations.  Table III already
# maps each claim to its method AND its scope, and the scope column is the part
# that answers the first-round report; a count cannot replace it.  The formal
# work appears here as one timeline row.
#
# Panel (a) carries, per campaign: the span from first to last recorded run, a
# mark per run-day with area by runs, the pre-registrations written before the
# runs they govern, and what the campaign produced.  Under it, the weekly
# density of runs.  July is empty and stays empty; nothing is drawn there that
# did not happen.
#
# Palette: house muted set, ordered navy -> mustard -> burgundy, the order that
# passes the colour-vision check (deltaE 20.0 deutan, 22.1 normal).  Three
# categorical slots; the six-slot house set fails CVD adjacency.
#
#   python mk_fig_scope_wide.py        # -> fig_scope_wide.pdf / .png
import os
import re
import csv
import glob
import json
import datetime as dt
import collections
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import rcParams
from matplotlib.patches import Rectangle, FancyBboxPatch
from matplotlib.lines import Line2D
from matplotlib.legend_handler import HandlerTuple
import matplotlib.patheffects as pe
import matplotlib.dates as mdates

rcParams["font.family"] = "Arial"
rcParams["font.size"] = 7
rcParams["axes.linewidth"] = 0.6
rcParams["pdf.fonttype"] = 42
rcParams["mathtext.fontset"] = "custom"
rcParams["mathtext.rm"] = "Arial"
rcParams["mathtext.it"] = "Arial:italic"

NAVY, MUST, BURG = "#25405c", "#b08428", "#8a3a45"
INK, MUTED, GRID, SURF = "#2a2f36", "#8b93a0", "#dfe3e8", "white"

HERE = os.path.dirname(os.path.abspath(__file__))
AP = os.path.normpath(os.path.join(HERE, "..", ".."))
RAW = os.path.join(AP, "02_results_raw")


def n_elections(d):
    """forced elections recorded under one campaign directory"""
    k = 0
    p = os.path.join(d, "elections.log")
    if os.path.exists(p):
        k += sum(1 for _ in open(p))
    for f in glob.glob(os.path.join(d, "**", "elections.csv"), recursive=True):
        k += sum(1 for _ in csv.DictReader(open(f)))
    return k


# ============================================================= (b) elections
G1, G2, G3 = ("closed-loop sweep", "zero-parameter threshold swap",
              "operator-supplied exclusion")
byN = collections.defaultdict(collections.Counter)
GUARD_N = GUARD_WON = VAN_WON = 0
excl = collections.Counter()

for f in sorted(glob.glob(os.path.join(RAW, "x1_N*", "elections.csv"))):
    if os.path.basename(os.path.dirname(f)).startswith("INVALID"):
        continue
    for r in csv.DictReader(open(f)):
        byN[int(r["N"])][G1] += 1
        if r["arm"] in ("B_oracle", "C_predictor"):
            GUARD_N += 1
            GUARD_WON += int(r["target_won"] == "1")
        elif r["arm"] == "A_vanilla":
            VAN_WON += int(r["target_won"] == "1")

ROW = re.compile(r"^([ABC]_\w+),(\d+),")
SWAP_ALL = 0
for f in sorted(glob.glob(os.path.join(RAW, "b20_sweep_20260903-162221",
                                       "x1_N*_run*.log"))):
    n = int(re.search(r"N(\d+)", os.path.basename(f)).group(1))
    for ln in open(f, errors="replace"):
        m = ROW.match(ln.strip())
        if not m:
            continue
        e = int(ln.strip().split(",")[6])
        SWAP_ALL += e
        if m.group(1) in ("A_vanilla", "C_predictor"):
            byN[n][G2] += e
        else:
            excl["threshold-swap arm not reported"] += e

JUNE_DIRS = ("ne26_*", "detection_latency_*", "mldetect_*", "finalsupp_*",
             "nsweep_*", "loadsweep_*", "leaderacq*", "leaderscn*",
             "votereject_*", "corrected_*")
for d, n in (("finalsupp_20260611-144542", 5), ("nsweep_N7_121812", 7),
             ("nsweep_N7_120309", 7),
             ("nsweep_N9_122911", 9), ("xhost_election_154824", 5),
             ("xhost_t2_180044", 5), ("xhost_t2_182159", 5),
             ("xhost_t2b_184054", 5)):
    byN[n][G3] += sum(1 for _ in open(os.path.join(RAW, d, "elections.log")))

for f in glob.glob(os.path.join(RAW, "r13*", "**", "elections.csv"), recursive=True):
    excl["eviction-policy ablation"] += sum(1 for _ in csv.DictReader(open(f)))
# 115333 only: no election in it changed the leader (live 0/10), so it
# carries no forced election to count.  120309 is now in the corpus above.
for d in ("nsweep_N7_115333",):
    p = os.path.join(RAW, d, "elections.log")
    if os.path.exists(p):
        excl["runs excluded by name"] += sum(1 for _ in open(p))

NS = [5, 7, 9, 11, 15, 21]
GROUPS = [(G1, NAVY), (G2, MUST), (G3, BURG)]
TOTAL_EL = sum(sum(c.values()) for c in byN.values())

# ============================================================ (d) leader cost
sev = [r for r in csv.DictReader(open(os.path.join(
    AP, "12_leader_severity", "results", "per_run_metrics.csv"))) if r["valid"] == "1"]


def frac(r, a):
    try:
        s, fl = float(r["%s_500_succ" % a]), float(r["%s_500_fail" % a])
    except Exception:
        return None
    return fl / (s + fl) if s + fl else None


def bucket(x):
    return 0 if x is None or x < 0.05 else (2 if x >= 0.95 else 1)


LEAD = [bucket(frac(r, "L_leader")) for r in sev]
FOLL = [bucket(frac(r, "F_follower")) for r in sev]
BCOL = [NAVY, MUST, BURG]
BNAME = ["under 5% failed", "5–95% failed", "stalled, 95–100%"]

# ========================================================== (c) adversaries
H1H3 = os.path.join(AP, "08_predictor", "r12_panel", "h1h3")
panel = json.load(open(os.path.join(AP, "08_predictor", "r12_panel",
                                    "panel2_results.json"), encoding="utf-8"))
PGD = len(panel) * len(panel[0]["sweep"]) * 36
adv2 = json.load(open(os.path.join(H1H3, "results_adv2.json"), encoding="utf-8"))
rules = json.load(open(os.path.join(H1H3, "results_rules_sweep.json"), encoding="utf-8"))
MIMICRY = len(adv2) * 3 + len(rules) * 3
EV_CELLS = 0
for p, seeds in (("r13p4_N7_0917-163626", {1, 2, 3, 4}),
                 ("r13p4_N7_0917-223327", {5, 6})):
    f = os.path.join(RAW, p, "cells.csv")
    if os.path.exists(f):
        EV_CELLS += sum(1 for r in csv.DictReader(open(f))
                        if int(r["seed"]) in seeds and r["demotions"] not in ("-", ""))
# Row 1 is the whole exclusion corpus, not one fault: 315 of the 1,515 are
# the operator-supplied campaign, which carries no injected delay, as
# Fig. 5(a)'s caption states.  Labelling the row "+200 ms" contradicted it.
# Row 3 drops the beta: the text uses beta for consistency/robustness and
# never defines a mimicry beta, so one letter was carrying two meanings.
ADV = [("exclusion corpus", TOTAL_EL, "forced elections", NAVY),
       ("injected false positives", EV_CELLS, "policy cells", NAVY),
       ("mimicry sweep, 0 to full", MIMICRY, "advisor-seed cells", MUST),
       ("white-box PGD", PGD, "attack runs", MUST)]

# ========================================================== (a) every election
# One cell per forced election of the two sweeps, from the per-election rows of
# x1_N*/elections.csv and the per-seed summary rows of the threshold swap's run
# logs.  Nothing is aggregated away: 1,440 cells, 1,440 elections.
OB = sum(int(m.group(2)) for m in re.finditer(
    r"^\s*(\S+)\s+(\d+)/\2\s+EXIT=0",
    open(os.path.join(AP, "05_formal", "tla", "PROOF_RESULT.txt"),
         encoding="utf-8").read(), re.M))

CELL_N = [7, 9, 11, 15, 21]
# outcome[campaign][arm][N] -> list of 0 (excluded) / 1 (acquired) / 2 (no leader)
outcome = {c: {a: {n: [] for n in CELL_N} for a in
               ("A_vanilla", "B_oracle", "C_predictor")}
           for c in ("sweep", "swap")}

# budget[campaign][arm][N] -> (|B_t|, cap); exact[campaign][arm] -> B_t == the
# degraded set, counted; early[campaign][arm] -> elections that began before the
# detector had published a list.
budget = {c: {a: {} for a in ("A_vanilla", "B_oracle", "C_predictor")}
          for c in ("sweep", "swap")}
exact = collections.Counter()
early = collections.Counter()


def _set(s, seps=";,[]"):
    for ch in seps[2:]:
        s = s.replace(ch, "")
    return set(x for x in s.replace(",", ";").split(";") if x.strip())


for f in sorted(glob.glob(os.path.join(RAW, "x1_N*", "elections.csv"))):
    if os.path.basename(os.path.dirname(f)).startswith("INVALID"):
        continue
    for r in csv.DictReader(open(f)):
        n, a = int(r["N"]), r["arm"]
        v = 1 if r["target_won"] == "1" else (2 if r["live"] == "0" else 0)
        outcome["sweep"][a][n].append(v)
        if r["window"] != "W1":
            early[("sweep", a)] += 1
        if a == "A_vanilla":
            continue
        if _set(r["list"]) == _set(r["targets"]):
            exact[("sweep", a)] += 1
        if r["cap"] not in ("", "NA"):
            budget["sweep"][a][n] = (int(r["size"]), int(r["cap"]))

SROW = re.compile(r"^([ABC]_\w+),(\d+),")
for f in sorted(glob.glob(os.path.join(RAW, "b20_sweep_20260903-162221",
                                       "x1_N*_run*.log"))):
    for ln in open(f, errors="replace"):
        m = SROW.match(ln.strip())
        if not m:
            continue
        p = ln.strip().split(",")
        arm, n = m.group(1), int(m.group(2))
        e, won, live = int(p[6]), int(p[5]), int(p[7])
        outcome["swap"][arm][n] += [1] * won + [2] * (e - live) + \
                                   [0] * (e - won - (e - live))
        early[("swap", arm)] += int(p[8]) + int(p[9])
    head = open(f, errors="replace").read(4000)
    hm = re.search(r"^X1 closed loop: N=(\d+).*?targets=\[([^\]]*)\]", head, re.M)
    cm = re.search(r"daemon gate OK:.*?\bcap=(\d+)", head)
    if hm and cm:
        nn, mm, cp = int(hm.group(1)), len(_set(hm.group(2))), int(cm.group(1))
        for a in ("B_oracle", "C_predictor"):
            budget["swap"][a][nn] = (mm, cp)

BLOCKS = [("sweep", "A_vanilla", "no guard"),
          ("sweep", "B_oracle", "operator blacklist"),
          ("sweep", "C_predictor", "detector blacklist"),
          ("swap", "A_vanilla", "no guard"),
          ("swap", "B_oracle", "operator blacklist"),
          ("swap", "C_predictor", "zero-parameter threshold")]
CAMP = {"sweep": "closed-loop sweep", "swap": "threshold swap"}
CELLS = sum(len(outcome[c][a][n]) for c, a, _ in BLOCKS for n in CELL_N)
ACQ = sum(v == 1 for c, a, _ in BLOCKS for n in CELL_N for v in outcome[c][a][n])
NOLEAD = sum(v == 2 for c, a, _ in BLOCKS for n in CELL_N for v in outcome[c][a][n])

# ==================================================================== figure
fig = plt.figure(figsize=(7.16, 4.42))
topg = fig.add_gridspec(1, 1, left=0.150, right=0.988, top=0.945, bottom=0.395)
axA = fig.add_subplot(topg[0])
botg = fig.add_gridspec(1, 3, width_ratios=[1.06, 0.92, 1.02],
                        left=0.208, right=0.988, top=0.282, bottom=0.108,
                        wspace=0.56)
axB = fig.add_subplot(botg[0])
axC = fig.add_subplot(botg[1])
axD = fig.add_subplot(botg[2])

# ---- (a) one cell per forced election --------------------------------------
NCOLS = 20                          # cells across one block
OCOL = [NAVY, BURG, MUST]
ROWS_PER_BLOCK = sum(max(1, len(outcome["sweep"]["A_vanilla"][n]) // NCOLS)
                     for n in CELL_N) + 0.5 * (len(CELL_N) - 1)
BLOCK_W = NCOLS + 12.5              # block pitch, x  (gap carries the gauges)
BLOCK_H = ROWS_PER_BLOCK + 6.2      # block pitch, y
GX = NCOLS + 2.1                    # gauge column, offset from the block
FACT = {("sweep", "A_vanilla"): "no advice in force",
        ("swap", "A_vanilla"): "no advice in force",
        ("sweep", "B_oracle"): "matched the degraded set, %d/240",
        ("sweep", "C_predictor"): "matched the degraded set, %d/240",
        ("swap", "B_oracle"): "%d of 240 began before detection",
        ("swap", "C_predictor"): "%d of 240 began before detection"}
for bi, (camp, arm, lab) in enumerate(BLOCKS):
    bx = (bi % 3) * BLOCK_W
    by = (bi // 3) * BLOCK_H
    y, acq = 0, 0
    for n in CELL_N:
        vals = outcome[camp][arm][n]
        acq += sum(v == 1 for v in vals)
        for k, v in enumerate(vals):
            _blk = (k % NCOLS) // 10 + (k // NCOLS)    # seed-block parity
            _gap = 0.7 if (k % NCOLS) >= 10 else 0.0
            _al = 0.95 if v else (0.78 if _blk % 2 == 0 else 0.55)
            axA.add_patch(Rectangle((bx + (k % NCOLS) * 1.0 + _gap,
                                     by + y + (k // NCOLS) * 1.0), 0.80, 0.80,
                                    facecolor=OCOL[v], linewidth=0, alpha=_al))
        rows = max(1, len(vals) // NCOLS)
        if bi % 3 == 0:
            axA.text(bx - 0.8, by + y + rows / 2.0 - 0.1, "$N$=%d" % n, ha="right",
                     va="center", fontsize=6.2, color=MUTED)
        y += rows + 0.5
    # the advisory budget the guard actually held, one gauge per cluster size
    yy = 0
    for n in CELL_N:
        rows = max(1, len(outcome[camp][arm][n]) // NCOLS)
        bud = budget[camp][arm].get(n)
        if bud:
            sz, cp = bud
            cy = by + yy + rows / 2.0 - 0.45
            for k in range(cp):
                axA.add_patch(Rectangle((bx + GX + k * 0.66, cy), 0.48, 0.70,
                                        facecolor=NAVY if k < sz else "none",
                                        edgecolor=MUTED if k >= sz else "none",
                                        linewidth=0.4, alpha=0.9 if k < sz else 0.55))
            axA.text(bx + GX + cp * 0.66 + 0.55, cy + 0.35, "%d/%d" % (sz, cp),
                     ha="left", va="center", fontsize=6.4, color=MUTED)
        yy += rows + 0.5
    if budget[camp][arm]:
        axA.text(bx + GX, by - 2.40, "blacklist/cap", ha="left",
                 va="baseline", fontsize=6.2, color=MUTED)
    _lab = axA.text(bx, by - 3.75, lab, ha="left", va="baseline", fontsize=6.4,
                    color=INK)
    if (camp, arm) == ("swap", "B_oracle"):
        # drawn for completeness; Section V-D reports this campaign as 480
        UNREPORTED = (_lab, by - 3.75)
    axA.text(bx, by - 2.40, "%d acquired" % acq if acq else "none acquired",
             ha="left", va="baseline", fontsize=6.4,
             color=BURG if acq else MUTED, fontweight="bold" if acq else "normal")
    _f = FACT[(camp, arm)]
    if "%d" in _f:
        _f = _f % (exact[(camp, arm)] if camp == "sweep" else early[(camp, arm)])
    axA.text(bx, by - 1.05, _f, ha="left", va="baseline", fontsize=6.2,
             color=MUTED)
    if bi % 3 == 0:
        axA.text(bx - 5.4, by + ROWS_PER_BLOCK / 2.0 - 0.3, CAMP[camp],
                 ha="center", va="center", fontsize=6.8, color=INK, rotation=90)
axA.set_xlim(-6.6, 2 * BLOCK_W + GX + 9.6)
axA.set_ylim(2 * BLOCK_H - 4.4, -5.4)
axA.set_aspect("equal", adjustable="box")
axA.set_xticks([]); axA.set_yticks([])
for sp in ("top", "right", "left", "bottom"):
    axA.spines[sp].set_visible(False)

# ---- (b) elections by N ----------------------------------------------------
ypos = list(range(len(NS)))[::-1]
for yi, n in zip(ypos, NS):
    left = 0
    for gname, col in GROUPS:
        v = byN[n][gname]
        if not v:
            continue
        axB.barh(yi, v, left=left, height=0.62, color=col, alpha=0.88, linewidth=0)
        left += v
        axB.barh(yi, 5, left=left, height=0.62, color=SURF, linewidth=0)
        left += 5
    axB.text(left + 12, yi, f"{sum(byN[n].values()):,}", va="center", fontsize=6.2,
             color=INK)
axB.set_ylim(-0.62, len(NS) - 0.38)
axB.set_yticks(ypos)
axB.set_yticklabels([f"$N$={n}" for n in NS], fontsize=6.2)
axB.set_xlim(0, max(sum(byN[n].values()) for n in NS) * 1.24)
axB.set_xticks([0, 200, 400])
axB.tick_params(length=2, pad=2, labelsize=6.2)
for sp in ("top", "right", "left"):
    axB.spines[sp].set_visible(False)
axB.xaxis.grid(True, color=GRID, lw=0.5)
axB.set_axisbelow(True)
axB.legend(handles=[Rectangle((0, 0), 1, 1, color=c, alpha=0.88) for _, c in GROUPS],
           labels=[g for g, _ in GROUPS], fontsize=6.2, frameon=False,
           loc="upper left", bbox_to_anchor=(-0.215, -0.16), ncol=1,
           handlelength=0.85, handleheight=0.8, labelspacing=0.16,
           borderpad=0, handletextpad=0.32)

# ---- (c) adversaries -------------------------------------------------------
# The unit each row counts goes under the row's name, on the left, not after
# the marker.  The axis is 130 px wide and the longest unit was 81 of them, so
# on the right the long units ran out of the panel and butted against (d).  On
# the left they cost nothing: each is narrower than the widest row name, which
# the gap to (b) already holds.  Only the value stays on the right, and a value
# is never wider than 22 px.
yv = list(range(len(ADV)))[::-1]
CLAB, CLEFT = [], []                         # checked against (c) and (b) below
_lx = -0.031                                 # the tick pad, in axes coords
for yi, (lab, v, unit, col) in zip(yv, ADV):
    axC.plot([1, v], [yi, yi], color=GRID, lw=0.8, zorder=1, solid_capstyle="round")
    axC.plot(v, yi, "o", ms=4.4, mfc=col, mec=SURF, mew=0.5, zorder=3)
    CLEFT += [axC.text(_lx, yi + 0.13, lab, transform=axC.get_yaxis_transform(),
                       ha="right", va="center", fontsize=6.2, color=INK),
              axC.text(_lx, yi - 0.20, unit, transform=axC.get_yaxis_transform(),
                       ha="right", va="center", fontsize=6.2, color=MUTED)]
    CLAB.append((v, axC.text(v * 1.30, yi, f"{v:,}", va="center",
                             fontsize=6.2, color=INK, zorder=4)))
axC.set_yticks(yv)
axC.set_yticklabels([""] * len(yv))
axC.set_xscale("log")
axC.set_xlim(0.8, 20000)   # room for the value label, not for data
axC.set_xticks([1, 10, 100, 1000])
axC.set_xticklabels(["1", "10", "100", "1,000"], fontsize=6.2)
axC.set_xlabel("evaluated, log scale \u2014 one unit per row", fontsize=6.2,
               color=MUTED, labelpad=1.5)
axC.set_ylim(-0.7, len(ADV) - 0.3)
axC.tick_params(length=2, pad=2)
for sp in ("top", "right", "left"):
    axC.spines[sp].set_visible(False)
axC.xaxis.grid(True, color=GRID, lw=0.5)
axC.set_axisbelow(True)

# ---- (d) leader cost -------------------------------------------------------
NCOL = 12
for ri, (data, lab, lcol) in enumerate(((FOLL, "delayed\nfollower", NAVY),
                                        (LEAD, "delayed\nleader", BURG))):
    base = 1 - ri
    for i, b in enumerate(sorted(data)):
        cx, cy = i % NCOL, i // NCOL
        axD.add_patch(Rectangle((cx, base * 4.0 + (2 - cy) * 1.0), 0.74, 0.74,
                                facecolor=BCOL[b], alpha=0.9, linewidth=0))
    axD.text(-0.6, base * 4.0 + 1.37, lab, ha="right", va="center", fontsize=6.2,
             color=lcol, linespacing=1.15)
    n_st = sum(1 for b in data if b == 2)
    axD.text(NCOL + 0.3, base * 4.0 + 1.37,
             ("%d of %d\nstalled" % (n_st, len(data))) if n_st else "none\nstalled",
             ha="left", va="center", fontsize=6.2, linespacing=1.15,
             color=BURG if n_st else MUTED)
axD.set_xlim(-0.6, NCOL + 3.6)
axD.set_ylim(-1.5, 7.2)
axD.set_aspect("equal", adjustable="box")
axD.set_xticks([]); axD.set_yticks([])
for sp in ("top", "right", "left", "bottom"):
    axD.spines[sp].set_visible(False)
axD.legend(handles=[Rectangle((0, 0), 1, 1, color=c, alpha=0.9) for c in BCOL],
           labels=BNAME, fontsize=6.2, frameon=False, loc="upper left",
           bbox_to_anchor=(-0.08, 0.10), ncol=1, handlelength=0.85,
           handleheight=0.8, labelspacing=0.16, borderpad=0, handletextpad=0.32)

fig.canvas.draw()
_r = fig.canvas.get_renderer()

# A label wider than its panel is not an error anywhere in matplotlib: it just
# runs into the neighbour, which is how (c)'s units reached (d).  Measured, so
# that a longer string later fails loudly instead of quietly.
_cx1 = axC.get_window_extent(renderer=_r).x1
for _v, _t in CLAB:
    _ov = _t.get_window_extent(renderer=_r).x1 - _cx1
    if _ov > 0:
        print("WARNING: (c) value %s overruns the panel by %.1f px"
              % (_t.get_text(), _ov))
# and on the left, against what (b) actually draws.  (c)'s row names have always
# reached over (b)'s axes box; that is harmless until they meet one of (b)'s
# end-of-bar labels, which is what happened on the bottom row, where N=21 fills
# the axis.  So compare ink with ink, not with the box.
for _t in CLEFT:
    _a = _t.get_window_extent(renderer=_r)
    for _bt in axB.texts:
        _b = _bt.get_window_extent(renderer=_r)
        if _a.x0 < _b.x1 and _b.x0 < _a.x1 and _a.y0 < _b.y1 and _b.y0 < _a.y1:
            print("WARNING: (c) label %r overlaps (b) label %r"
                  % (_t.get_text(), _bt.get_text()))

# the tag sits a fixed gap after the label, measured from the label as drawn
_lt, _ly = UNREPORTED
_x1 = axA.transData.inverted().transform(
    _lt.get_window_extent(renderer=_r).corners()[2])[0]
axA.text(_x1 + 1.6, _ly, "not reported as evidence", ha="left", va="baseline",
         fontsize=6.2, color=MUTED, style="italic")
_pa = axA.get_position()
fig.text(0.012, _pa.y1 + 0.036, "(a)", ha="left", va="bottom", fontsize=7.4,
         color=INK)
fig.text(0.052, _pa.y1 + 0.036, "every forced election of the two sweeps on the single-host "
         "testbed, one square each, by campaign, arm and cluster size",
         ha="left", va="bottom", fontsize=6.6, color=INK)
# The navy cells are drawn in two shades, so the navy key carries both: the
# banding is the seed block, not a second outcome, and the key has to say so
# or the reader infers a distinction that is not there.
_key = [(Rectangle((0, 0), 1, 1, color=NAVY, alpha=0.78),
         Rectangle((0, 0), 1, 1, color=NAVY, alpha=0.55)),
        Rectangle((0, 0), 1, 1, color=BURG, alpha=0.9),
        Rectangle((0, 0), 1, 1, color=MUST, alpha=0.9)]
_leg = fig.legend(handles=_key,
           labels=["leader replaced, target excluded "
                   "(shades alternate by seed block)",
                   "target acquired leadership",
                   "no leader inside the read window"],
           handler_map={tuple: HandlerTuple(ndivide=None, pad=0.18)},
           fontsize=6.2, frameon=False, loc="upper center",
           bbox_to_anchor=(0.5 * (_pa.x0 + _pa.x1), _pa.y0 + 0.008), ncol=3,
           handlelength=0.85, handleheight=0.8, columnspacing=1.3,
           borderpad=0, handletextpad=0.32)
fig.canvas.draw()
_lw = _leg.get_window_extent(renderer=fig.canvas.get_renderer())
print("legend width %.2f in of %.2f in figure (left %.3f, right %.3f)"
      % (_lw.width / fig.dpi, fig.get_figwidth(),
         _lw.x0 / (fig.dpi * fig.get_figwidth()),
         _lw.x1 / (fig.dpi * fig.get_figwidth())))
for ax, letter, title in ((axB, "(b)", "elections, by cluster size"),
                          (axC, "(c)", "what each evidence class covers"),
                          (axD, "(d)", "what the excluded node cost")):
    p = ax.get_position()
    fig.text(p.x0 - 0.082, p.y1 + 0.030, letter, ha="left", va="bottom",
             fontsize=7.4, color=INK)
    fig.text(p.x0 - 0.040, p.y1 + 0.030, title, ha="left", va="bottom",
             fontsize=6.4, color=INK)

OUT = os.path.join(HERE, "fig_scope_wide.pdf")
fig.savefig(OUT)
fig.savefig(OUT.replace(".pdf", ".png"), dpi=300)
print("saved", OUT)
print("panel (a): %d cells, %d acquired, %d without a leader" % (CELLS, ACQ, NOLEAD))
print("cited elections %d  guarded %d/%d  unguarded %d  PGD %d  obligations %d"
      % (TOTAL_EL, GUARD_WON, GUARD_N, VAN_WON, PGD, OB))
print("excluded from (b):", dict(excl), "=", sum(excl.values()))
