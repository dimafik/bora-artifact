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
OUT = r"D:\프랑스 업데이트\TNSE 스페셜이슈 논문\리비전\figures\fig_exclusion_2panel.pdf"


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

# closed-loop sweep: guarded = oracle + predictor arms pooled (2 x 40 per N)
RIGHT = [("$N{=}7$",  (3, 40), (0, 80)),
         ("$N{=}9$",  (5, 40), (0, 80)),
         ("$N{=}11$", (4, 40), (0, 80)),
         ("$N{=}15$", (4, 40), (0, 80)),
         ("$N{=}21$", (5, 80), (0, 160))]

fig, axes = plt.subplots(1, 2, figsize=(7.05, 2.55), sharex=True)

# Plain text titles on purpose: matplotlib mathtext with Arial does not carry a
# calligraphic face, so "$\mathcal{B}_t$" degrades silently to a bare "t".
for ax, cfgs, title in ((axes[0], LEFT, "(a) operator-supplied blacklist"),
                        (axes[1], RIGHT, "(b) detector-produced blacklist")):
    ys = list(range(len(cfgs)))[::-1]
    for y, (lab, (bk, bn), (ak, an)) in zip(ys, cfgs):
        bl, bu, bp = wilson(bk, bn)
        al, au, ap = wilson(ak, an)
        ax.plot([bl, bu], [y + 0.13] * 2, color=BURG, lw=1.4, solid_capstyle="round")
        ax.plot(bp, y + 0.13, "o", ms=4.5, color=BURG,
                markerfacecolor="white", markeredgewidth=1.1)
        ax.plot([al, au], [y - 0.13] * 2, color=NAVY, lw=1.4, solid_capstyle="round")
        ax.plot(ap, y - 0.13, "s", ms=4.2, color=NAVY)
        ax.text(au + 1.2, y - 0.13, "\u2264%.1f%%" % au, fontsize=6.8,
                color=NAVY, va="center")
    ax.set_yticks(ys)
    ax.set_yticklabels([c[0] for c in cfgs], fontsize=7.5)
    ax.set_ylim(-0.6, len(cfgs) - 0.4)
    ax.set_xlim(-2, 62)
    ax.axvline(0, ls=(0, (4, 3)), lw=0.7, color=SLATE, alpha=0.6)
    ax.grid(True, axis="x", lw=0.4, alpha=0.35)
    ax.set_title(title, fontsize=8)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)

axes[0].set_xlabel("Leadership acquisition (%), 95% Wilson CI", fontsize=8)
axes[1].set_xlabel("Leadership acquisition (%), 95% Wilson CI", fontsize=8)
axes[1].legend(handles=[
    Line2D([0], [0], color=BURG, marker="o", markerfacecolor="white", lw=1.4,
           label="no advice"),
    Line2D([0], [0], color=NAVY, marker="s", lw=1.4, label="BORA")],
    loc="lower right", fontsize=7, frameon=False, handlelength=1.6)

fig.tight_layout(pad=0.4)
fig.savefig(OUT, bbox_inches="tight")
print("saved:", OUT)
print("* the two starred rows are the only points whose target carries no delay")
