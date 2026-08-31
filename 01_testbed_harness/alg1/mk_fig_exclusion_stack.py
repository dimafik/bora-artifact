# Two-panel exclusion forest for the revision.
#
# WHY TWO PANELS. The single-panel figure put four configurations on one axis
# whose baselines were not measured the same way: N=5 and the AWS cluster carry a
# +200 ms delay on the target, while the N=7/N=9 scaling points came from
# nsweep.sh, which injects no delay at all -- its target is a HEALTHY orderer.
# Plotting them together is what made the "12.5-35%" range look like one
# quantity. It is also exactly what Reviewer 2 objected to: in every one of those
# runs the blacklist was supplied by the operator.
#
# Left panel  = operator-supplied blacklist (the original four configurations).
# Right panel = detector-produced blacklist (the closed-loop sweep), where the
#               target is degraded in every stratum and the blacklist comes from
#               the model rather than from us.
#
# Putting them side by side answers R2-1 visually: the two ways of obtaining the
# blacklist give the same exclusion.
#
# Palette and font follow make_g1_g2.py (academic muted, Arial, vector PDF).
import math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import rcParams
from matplotlib.lines import Line2D

rcParams["font.family"] = "Arial"
rcParams["font.size"] = 9
rcParams["axes.linewidth"] = 0.7
rcParams["pdf.fonttype"] = 42

NAVY = "#25405c"; BURG = "#8a3a45"; SLATE = "#5b6670"
OUT = r"D:\프랑스 업데이트\TNSE 스페셜이슈 논문\리비전\figures\fig_exclusion_stack.pdf"


def wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = (z / d) * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0, c - h) * 100, min(1, c + h) * 100, p * 100


# (label, baseline k/n, guarded k/n)
LEFT = [("$N{=}5$ single-host", (7, 36), (0, 36)),
        ("$N{=}7$ scaling*",    (7, 20), (0, 20)),
        ("$N{=}9$ scaling*",    (4, 20), (0, 20)),
        ("physical 5-host AWS", (2, 16), (0, 16))]

# Closed-loop sweep.  The two guarded arms are shown SEPARATELY.  Pooling them
# into one 0/80 point was the earlier presentation and it was wrong to label
# that point "detector-produced": half of every pooled count came from the
# operator-supplied arm, which is exactly the conflation Reviewer 2 objected to.
# Split apart, the figure makes the real claim visible -- the two arms land on
# top of each other -- instead of hiding it inside an aggregate.
# (label, no-advice k/n, operator-supplied k/n, detector-produced k/n)
RIGHT = [("$N{=}7$",  (3, 40), (0, 40), (0, 40)),
         ("$N{=}9$",  (5, 40), (0, 40), (0, 40)),
         ("$N{=}11$", (4, 40), (0, 40), (0, 40)),
         ("$N{=}15$", (4, 40), (0, 40), (0, 40)),
         ("$N{=}21$", (5, 80), (0, 80), (0, 80))]

fig, axes = plt.subplots(2, 1, figsize=(3.45, 4.30), sharex=True)

# Plain text titles on purpose: matplotlib mathtext with Arial does not carry a
# calligraphic face, so "$\mathcal{B}_t$" degrades silently to a bare "t".
for ax, cfgs, title in ((axes[0], LEFT, "(a) operator-supplied blacklist"),
                        (axes[1], RIGHT, "(b) closed-loop sweep, arms separated")):
    ys = list(range(len(cfgs)))[::-1]
    for y, row in zip(ys, cfgs):
        lab, arms = row[0], row[1:]
        # one row = 2 arms (panel a) or 3 arms (panel b); offsets centre the group
        style = [(BURG, "o", "white", 4.5), (NAVY, "s", NAVY, 4.2)] if len(arms) == 2 \
            else [(BURG, "o", "white", 4.5), (SLATE, "^", "white", 4.4),
                  (NAVY, "s", NAVY, 4.2)]
        span = 0.13 if len(arms) == 2 else 0.21
        offs = [span - i * (2 * span / (len(arms) - 1)) for i in range(len(arms))]
        zero = {}
        for (k, n), (col, mk, fc, ms), dy in zip(arms, style, offs):
            lo, hi, pt = wilson(k, n)
            ax.plot([lo, hi], [y + dy] * 2, color=col, lw=1.4, solid_capstyle="round")
            ax.plot(pt, y + dy, mk, ms=ms, color=col,
                    markerfacecolor=fc, markeredgewidth=1.1)
            if k == 0:
                # key on the printed string: two arms that round to the same
                # bound get one label, not two overprinted ones
                zero.setdefault("\u2264%.1f%%" % hi, []).append((hi, dy, col))
        for txt, hits in zero.items():
            hi = max(h for h, _, _ in hits)
            dy = sum(d for _, d, _ in hits) / len(hits)
            col = hits[-1][2]
            ax.text(hi + 1.2, y + dy, txt, fontsize=6.8, color=col, va="center")
    ax.set_yticks(ys)
    ax.set_yticklabels([c[0] for c in cfgs], fontsize=7.5)
    ax.set_ylim(-0.6, len(cfgs) - 0.4)
    ax.set_xlim(-2, 62)
    ax.axvline(0, ls=(0, (4, 3)), lw=0.7, color=SLATE, alpha=0.6)
    ax.grid(True, axis="x", lw=0.4, alpha=0.35)
    ax.set_title(title, fontsize=8)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)

axes[0].set_xlabel("")
axes[1].set_xlabel("Leadership acquisition (%), 95% Wilson CI", fontsize=8)
axes[1].legend(handles=[
    Line2D([0], [0], color=BURG, marker="o", markerfacecolor="white", lw=1.4,
           label="no advice"),
    Line2D([0], [0], color=SLATE, marker="^", markerfacecolor="white", lw=1.4,
           label="operator-supplied"),
    Line2D([0], [0], color=NAVY, marker="s", lw=1.4, label="detector-produced")],
    loc="lower right", fontsize=6.5, frameon=False, handlelength=1.6)

fig.tight_layout(pad=0.4)
fig.savefig(OUT, bbox_inches="tight")
print("saved:", OUT)
print("* the two starred rows are the only points whose target carries no delay")
