# Campaign scope, drawn from the artefact.  Single column, for the body.
#
# Reviewer 2 rejected the first round on one sentence: the claims are "not fully
# matched by the actual scope of the model, the formalization, and the empirical
# evidence."  The formalization axis is answered by Table III, whose Scope column
# states what each result is proved over; a figure of obligation counts cannot
# replace that and is not attempted here.  The manuscript has no figure for the
# other two axes, so this one carries them:
#
#   (a) empirical -- every forced leader election the manuscript cites as
#                    exclusion evidence, by cluster size and campaign.
#   (b) model     -- what the excluded node would have cost, one mark per run.
#
# Panel (a) counts CITED evidence only.  Excluded, and stated in the caption:
# the eviction-policy ablation (a different question), the threshold-swap oracle
# arm the paper does not report, and the two runs the manuscript excludes by
# name.  An earlier draft headlined all 2,779 recorded elections; a reviewer who
# opened the artefact would have found that 45% of them answer something else,
# which is the exact shape of the complaint this figure exists to answer.
#
# Every number is read from a results file at run time, so the figure cannot
# drift from the data.
#
# Palette: the house muted set, ordered navy -> mustard -> burgundy, the order
# that passes the colour-vision check (deltaE 20.0 deutan, 22.1 normal vision).
# Three slots only; the six-slot house set fails CVD adjacency.
#
#   python mk_fig_campaign.py          # -> fig_scope.pdf / .png
import os
import re
import csv
import glob
import collections
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import rcParams
from matplotlib.patches import Rectangle

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

G1, G2, G3 = ("closed-loop sweep", "zero-parameter threshold swap",
              "operator-supplied exclusion")
byN = collections.defaultdict(collections.Counter)
excl = collections.Counter()
GUARD_N = GUARD_WON = VAN_WON = 0

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
for f in sorted(glob.glob(os.path.join(RAW, "b20_sweep_20260903-162221",
                                       "x1_N*_run*.log"))):
    n = int(re.search(r"N(\d+)", os.path.basename(f)).group(1))
    for ln in open(f, errors="replace"):
        m = ROW.match(ln.strip())
        if not m:
            continue
        e = int(ln.strip().split(",")[6])
        if m.group(1) in ("A_vanilla", "C_predictor"):
            byN[n][G2] += e
        else:
            excl["threshold-swap oracle arm, not reported"] += e

for d, n in (("finalsupp_20260611-144542", 5), ("nsweep_N7_121812", 7),
             ("nsweep_N9_122911", 9), ("xhost_election_154824", 5),
             ("xhost_t2_180044", 5), ("xhost_t2_182159", 5),
             ("xhost_t2b_184054", 5)):
    byN[n][G3] += sum(1 for _ in open(os.path.join(RAW, d, "elections.log")))

for f in glob.glob(os.path.join(RAW, "r13*", "**", "elections.csv"), recursive=True):
    excl["eviction-policy ablation"] += sum(1 for _ in csv.DictReader(open(f)))
for d in ("nsweep_N7_115333", "nsweep_N7_120309"):
    p = os.path.join(RAW, d, "elections.log")
    if os.path.exists(p):
        excl["runs excluded by name"] += sum(1 for _ in open(p))

NS = [5, 7, 9, 11, 15, 21]
GROUPS = [(G1, NAVY), (G2, MUST), (G3, BURG)]
TOTAL_EL = sum(sum(c.values()) for c in byN.values())

# ------------------------------------------------------------------ severity
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

# --------------------------------------------------------------------- figure
fig = plt.figure(figsize=(3.45, 3.28))
gs = fig.add_gridspec(2, 1, height_ratios=[1.0, 0.66], left=0.245, right=0.985,
                      top=0.845, bottom=0.050, hspace=0.80)
axA = fig.add_subplot(gs[0])
axC = fig.add_subplot(gs[1])

ypos = list(range(len(NS)))[::-1]
for yi, n in zip(ypos, NS):
    left = 0
    for gname, col in GROUPS:
        v = byN[n][gname]
        if not v:
            continue
        axA.barh(yi, v, left=left, height=0.64, color=col, alpha=0.88, linewidth=0)
        left += v
        axA.barh(yi, 4, left=left, height=0.64, color=SURF, linewidth=0)
        left += 4
    axA.text(left + 10, yi, f"{sum(byN[n].values()):,}", va="center", fontsize=6.2,
             color=INK)
axA.set_ylim(-0.62, len(NS) - 0.38)
axA.set_yticks(ypos)
axA.set_yticklabels([f"$N$ = {n}" for n in NS], fontsize=6.6)
axA.set_xlim(0, max(sum(byN[n].values()) for n in NS) * 1.22)
axA.set_xticks([0, 200, 400])
axA.tick_params(length=2, pad=2, labelsize=6.0)
axA.set_xlabel("forced leader elections", fontsize=6.4, labelpad=1.0)
for sp in ("top", "right", "left"):
    axA.spines[sp].set_visible(False)
axA.xaxis.grid(True, color=GRID, lw=0.5)
axA.set_axisbelow(True)
axA.legend(handles=[Rectangle((0, 0), 1, 1, color=c, alpha=0.88) for _, c in GROUPS],
           labels=[g for g, _ in GROUPS], fontsize=5.7, frameon=False,
           loc="upper left", bbox_to_anchor=(-0.245, -0.235), ncol=1,
           handlelength=0.9, handleheight=0.8, labelspacing=0.2,
           borderpad=0, handletextpad=0.35)
fig.text(0.020, 0.975, "(a)", ha="left", va="top", fontsize=7.2, color=INK)
fig.text(0.105, 0.975, "%d guarded elections, %d acquisitions"
         % (GUARD_N, GUARD_WON), ha="left", va="top", fontsize=6.3, color=BURG,
         fontweight="bold")
fig.text(0.105, 0.930, "against %d unguarded  ·  %s cited elections in all"
         % (VAN_WON, f"{TOTAL_EL:,}"), ha="left", va="top", fontsize=5.8,
         color=MUTED)

NCOL = 12
for ri, (data, lab, lcol) in enumerate(((FOLL, "delayed\nfollower", NAVY),
                                        (LEAD, "delayed\nleader", BURG))):
    base = 1 - ri
    for i, b in enumerate(sorted(data)):
        cx, cy = i % NCOL, i // NCOL
        axC.add_patch(Rectangle((cx, base * 4.0 + (2 - cy) * 1.0), 0.74, 0.74,
                                facecolor=BCOL[b], alpha=0.9, linewidth=0))
    axC.text(-0.6, base * 4.0 + 1.37, lab, ha="right", va="center", fontsize=6.2,
             color=lcol, linespacing=1.15)
    n_st = sum(1 for b in data if b == 2)
    axC.text(NCOL + 0.3, base * 4.0 + 1.37,
             ("%d of %d\nstalled" % (n_st, len(data))) if n_st else "none\nstalled",
             ha="left", va="center", fontsize=5.9, linespacing=1.15,
             color=BURG if n_st else MUTED)
axC.set_xlim(-0.6, NCOL + 3.6)
axC.set_ylim(-1.15, 7.2)
axC.set_aspect("equal", adjustable="box")
axC.set_xticks([]); axC.set_yticks([])
for sp in ("top", "right", "left", "bottom"):
    axC.spines[sp].set_visible(False)
# set_aspect("equal") shrinks axC's box, so its axes-relative coordinates no
# longer line up with panel (a).  Draw once, read the box back, and place the
# header in figure coordinates at the same left margin as (a).
fig.canvas.draw()
_p = axC.get_position()
fig.text(0.020, _p.y1 + 0.028, "(b)", ha="left", va="bottom", fontsize=7.2, color=INK)
fig.text(0.105, _p.y1 + 0.028, "one square = one paired run at 500 tx/s",
         ha="left", va="bottom", fontsize=6.2, color=INK)
axC.legend(handles=[Rectangle((0, 0), 1, 1, color=c, alpha=0.9) for c in BCOL],
           labels=BNAME, fontsize=5.7, frameon=False, loc="upper left",
           bbox_to_anchor=(-0.115, 0.035), ncol=3, handlelength=0.85,
           handleheight=0.8, labelspacing=0.18, columnspacing=0.55,
           borderpad=0, handletextpad=0.3)

OUT = os.path.join(HERE, "fig_scope.pdf")
fig.savefig(OUT)
fig.savefig(OUT.replace(".pdf", ".png"), dpi=300)
print("saved", OUT)
print("cited elections %d   guarded %d/%d   unguarded acquisitions %d"
      % (TOTAL_EL, GUARD_WON, GUARD_N, VAN_WON))
print("by N:", {n: dict(byN[n]) for n in NS})
print("excluded:", dict(excl), "=", sum(excl.values()))
print("severity  leader:", collections.Counter(LEAD), " follower:", collections.Counter(FOLL))
