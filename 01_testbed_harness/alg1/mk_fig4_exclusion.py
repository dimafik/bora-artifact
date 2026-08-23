"""Regenerate Fig.4 (fig_exclusion_forest.pdf) to MATCH the other graph
figures: same aspect (~0.70, like loadsweep/detect), Arial + muted academic
palette (navy/burgundy), legend INSIDE the axes so the tight bbox is not
widened. Data verbatim from the manuscript (real Wilson intervals).
Output: figures/fig_exclusion_forest.pdf"""
import numpy as np
import matplotlib as mpl
mpl.use("Agg")
mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "pdf.fonttype": 42, "ps.fonttype": 42,
    "axes.linewidth": 0.8, "axes.edgecolor": "#2b2b2b",
    "axes.labelsize": 8.3, "xtick.labelsize": 7.3, "ytick.labelsize": 7.6,
    "legend.fontsize": 7.0, "legend.frameon": False,
})
import matplotlib.pyplot as plt
from matplotlib.ticker import AutoMinorLocator

NAVY = "#25405c"; BURG = "#8a3a45"; GREY = "#9aa3ab"
OUT = r"D:\프랑스 업데이트\TNSE 스페셜이슈 논문\IS-Raft-LAC\submission\figures"


def wilson(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = (z / d) * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, c - h), min(1.0, c + h), p


# real data, verbatim from manuscript
cfgs = [
    (r"$N{=}5$ single-host", (7, 36), (0, 36)),
    (r"$N{=}7$",             (7, 20), (0, 20)),
    (r"$N{=}9$",             (4, 20), (0, 20)),
    (r"5-host AWS",          (2, 16), (0, 16)),
]

# figsize aspect ~0.70 to match the other single-panel graphs
fig, ax = plt.subplots(figsize=(3.5, 2.5))
fig.subplots_adjust(left=0.30, right=0.965, top=0.90, bottom=0.18)
ys = np.arange(len(cfgs))[::-1]
for y, (name, (kb, nb), (kr, nr)) in zip(ys, cfgs):
    lo, hi, p = wilson(kb, nb)
    ax.plot([lo * 100, hi * 100], [y + 0.16] * 2, color=BURG, lw=1.6,
            solid_capstyle="round", zorder=3)
    for xx in (lo * 100, hi * 100):
        ax.plot([xx, xx], [y + 0.16 - 0.07, y + 0.16 + 0.07], color=BURG, lw=1.2, zorder=3)
    ax.scatter([p * 100], [y + 0.16], s=34, color=BURG, zorder=4,
               edgecolor="white", lw=0.6)
    ax.text(p * 100, y + 0.16 + 0.14, f"{p*100:.1f}%", va="bottom", ha="center",
            fontsize=6.5, color=BURG)
    lo2, hi2, p2 = wilson(kr, nr)
    ax.plot([lo2 * 100, hi2 * 100], [y - 0.16] * 2, color=NAVY, lw=1.6,
            solid_capstyle="round", zorder=3)
    ax.plot([hi2 * 100, hi2 * 100], [y - 0.16 - 0.07, y - 0.16 + 0.07], color=NAVY, lw=1.2, zorder=3)
    ax.scatter([p2 * 100], [y - 0.16], s=34, marker="D", color=NAVY, zorder=4,
               edgecolor="white", lw=0.6)
    ax.text(hi2 * 100 + 0.8, y - 0.16, f"0% [0, {hi2*100:.1f}]", va="center",
            ha="left", fontsize=6.5, color=NAVY)
ax.set_yticks(ys); ax.set_yticklabels([c[0] for c in cfgs])
ax.set_xlabel("Targeted-orderer leadership-acquisition rate (%)")
ax.set_xlim(-2, 60); ax.set_ylim(-0.7, len(cfgs) - 0.3)
ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
ax.xaxis.set_minor_locator(AutoMinorLocator(2))
ax.tick_params(which="both", length=3, width=0.7, color="#555")
ax.tick_params(which="minor", length=1.6)
ax.xaxis.grid(True, ls=(0, (3, 3)), lw=0.6, color=GREY, alpha=0.8)
ax.set_axisbelow(True)

# legend INSIDE the axes (empty upper-right region) -> tight bbox not widened
h1 = ax.scatter([], [], s=34, color=BURG, edgecolor="white", lw=0.6, label="baseline Raft")
h2 = ax.scatter([], [], s=34, marker="D", color=NAVY, edgecolor="white", lw=0.6, label="BORA")
ax.legend(handles=[h1, h2], loc="lower right", bbox_to_anchor=(0.995, 1.0),
          ncol=2, columnspacing=1.1, handletextpad=0.4)

fig.savefig(OUT + r"\fig_exclusion_forest.pdf")
fig.savefig(OUT + r"\fig_exclusion_forest.png", dpi=200)
plt.close(fig)
print("wrote fig_exclusion_forest.pdf (Arial, muted, aspect-matched, legend inside)")
