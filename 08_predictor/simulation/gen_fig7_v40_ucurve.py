"""
gen_fig7_v40_ucurve.py - NE16 capacity U-curve ("bigger is not
better") on PBFT moment-matched. Transformer trained at 6 capacity
points x 3 seeds.

Panel A (left, 3D): capacity x seed x AUC landscape with three
shaded regions (under-capacity, right-sized, over-capacity) and
mean ridge + min/max envelope.

Panel B (right, 2D): per-capacity AUC bars with std error bars,
coefficient-of-variation (std/mean) as colored badges, and
explicit "right-sized regime" annotation aligned with the
Theorem 3 corollary on minimum-sufficient function class.
"""
from __future__ import annotations
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, FancyBboxPatch
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "figures"
OUT.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 8.5,
    "axes.titlesize": 9,
    "axes.labelsize": 8,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "legend.fontsize": 7,
    "axes.linewidth": 0.6,
    "lines.linewidth": 1.2,
    "savefig.dpi": 300,
    "figure.dpi": 150,
})

# NE16 measurements (params, auc_mean, auc_std, auc_min, auc_max,
# label)
NE16 = [
    (2273,   1.0000, 0.0000, 1.0000, 1.0000, "S1"),
    (17185,  0.9999, 0.0001, 0.9998, 1.0000, "S2"),
    (38065,  0.9991, 0.0013, 0.9973, 1.0000, "S3"),
    (100609, 0.8730, 0.1748, 0.6258, 0.9999, "S4"),
    (134081, 0.9865, 0.0180, 0.9611, 1.0000, "S5"),
    (299425, 0.8352, 0.1207, 0.6698, 0.9544, "S6"),
]

# Regime boundaries (log10 of params)
RIGHT_SIZED_LO = 3.0   # 10^3
RIGHT_SIZED_HI = 4.7   # 5 x 10^4
TRANSITION_HI  = 5.3   # 2 x 10^5


def panel_A(ax):
    # 3D ridge with seed dimension as Y axis
    params = np.array([r[0] for r in NE16])
    means = np.array([r[1] for r in NE16])
    stds = np.array([r[2] for r in NE16])
    mins = np.array([r[3] for r in NE16])
    maxs = np.array([r[4] for r in NE16])
    logp = np.log10(params)

    # Background regime shading at z=0.45 (below the curves)
    z_floor = 0.45
    # under-capacity (logp < 3.0) red translucent
    xg_u = np.linspace(2.7, RIGHT_SIZED_LO, 4)
    # right-sized green
    xg_r = np.linspace(RIGHT_SIZED_LO, RIGHT_SIZED_HI, 8)
    # transition yellow
    xg_t = np.linspace(RIGHT_SIZED_HI, TRANSITION_HI, 6)
    # over-capacity orange
    xg_o = np.linspace(TRANSITION_HI, 6.0, 4)
    yg = np.linspace(-0.5, 3.5, 6)

    def fill_band(xrange, color, alpha):
        XG, YG = np.meshgrid(xrange, yg)
        ZG = np.full_like(XG, z_floor)
        ax.plot_surface(XG, YG, ZG, color=color, alpha=alpha,
                        rstride=1, cstride=1, linewidth=0,
                        antialiased=False, shade=False)

    fill_band(xg_u, "#ffcdc4", 0.30)
    fill_band(xg_r, "#c8e6c9", 0.42)
    fill_band(xg_t, "#fff3b8", 0.32)
    fill_band(xg_o, "#ffd09e", 0.32)

    # Theorem 1 ceiling at 0.5
    XG2 = np.linspace(2.7, 6.0, 12)
    YG2 = np.linspace(-0.5, 3.5, 6)
    XX, YY = np.meshgrid(XG2, YG2)
    ZZ_thm1 = np.full_like(XX, 0.5)
    ax.plot_surface(XX, YY, ZZ_thm1, color="#ff6b3d", alpha=0.10,
                    rstride=1, cstride=1, linewidth=0,
                    antialiased=False, shade=False)
    ZZ_perf = np.full_like(XX, 1.0)
    ax.plot_surface(XX, YY, ZZ_perf, color="#0d4f4f", alpha=0.05,
                    rstride=1, cstride=1, linewidth=0,
                    antialiased=False, shade=False)

    # min/max envelope as ribbon (3 seeds depicted as ymin/ymax)
    # We'll show min at y=0.0 and max at y=2.0; mean at y=1.0
    y_min, y_mean, y_max = 0.0, 1.5, 3.0
    # Connect with vertical lines
    for i, lp in enumerate(logp):
        ax.plot([lp, lp], [y_min, y_max], [mins[i], maxs[i]],
                color="#1f4e79", lw=0.8, alpha=0.6)
    # Min trace
    ax.plot(logp, np.full_like(logp, y_min), mins,
            color="#1f4e79", lw=1.2, marker="v", markersize=5,
            label="min seed", alpha=0.65)
    # Max trace
    ax.plot(logp, np.full_like(logp, y_max), maxs,
            color="#1f4e79", lw=1.2, marker="^", markersize=5,
            label="max seed", alpha=0.65)
    # Mean trace (thick blue) on center
    ax.plot(logp, np.full_like(logp, y_mean), means,
            color="#003d6b", lw=2.5, marker="o", markersize=7,
            markerfacecolor="#1f4e79",
            markeredgecolor="#003d6b", markeredgewidth=0.6,
            zorder=10, label="mean")

    # Drop columns from mean down to floor for capacity-axis link
    for i, lp in enumerate(logp):
        ax.plot([lp, lp], [y_mean, y_mean], [z_floor, means[i]],
                color="#003d6b", lw=0.4, linestyle=":", alpha=0.5)

    # Annotate right-sized regime
    ax.text(3.6, 1.5, 1.06, "right-sized regime",
            color="#005500", fontsize=7.5, ha="center",
            weight="bold", style="italic")
    ax.text(5.1, 1.5, 1.06, "over-capacity",
            color="#c55a11", fontsize=7.5, ha="center",
            weight="bold", style="italic")

    ax.set_xlabel(r"$\log_{10}$(parameters)", labelpad=2)
    ax.set_ylabel("seed-axis", labelpad=-4)
    ax.set_zlabel("AUC", labelpad=-2)
    ax.set_yticks([y_min, y_mean, y_max])
    ax.set_yticklabels(["min", "mean", "max"], fontsize=6.5)
    ax.set_zlim(z_floor, 1.08)
    ax.set_xlim(2.7, 6.0)
    ax.view_init(elev=22, azim=-60)
    ax.tick_params(axis="x", pad=-2)
    ax.tick_params(axis="y", pad=-1)
    ax.tick_params(axis="z", pad=-1)
    ax.xaxis.pane.set_facecolor("#f8f8fc")
    ax.yaxis.pane.set_facecolor("#f8f8fc")
    ax.zaxis.pane.set_facecolor("#ffffff")
    ax.xaxis.pane.set_edgecolor("#cccccc")
    ax.yaxis.pane.set_edgecolor("#cccccc")
    ax.zaxis.pane.set_edgecolor("#cccccc")
    ax.grid(True, linestyle=":", alpha=0.25)
    ax.set_title(r"(a) 3-D U-curve: capacity $\times$ seed $\times$ AUC",
                 pad=4, fontsize=9, weight="bold")


def panel_B(ax):
    # 2D bar chart with regime shading
    params = np.array([r[0] for r in NE16])
    means = np.array([r[1] for r in NE16])
    stds = np.array([r[2] for r in NE16])
    labels = [r[5] for r in NE16]
    logp = np.log10(params)

    # Shade regimes on the y range
    ax.axvspan(2.7, RIGHT_SIZED_LO, color="#ffcdc4", alpha=0.25,
               zorder=0)
    ax.axvspan(RIGHT_SIZED_LO, RIGHT_SIZED_HI, color="#c8e6c9",
               alpha=0.35, zorder=0)
    ax.axvspan(RIGHT_SIZED_HI, TRANSITION_HI, color="#fff3b8",
               alpha=0.30, zorder=0)
    ax.axvspan(TRANSITION_HI, 6.0, color="#ffd09e", alpha=0.30,
               zorder=0)

    # Regime labels at top
    ax.text((2.7+RIGHT_SIZED_LO)/2, 1.06, "under-\ncapacity",
            fontsize=6.5, color="#a01700", ha="center",
            style="italic", weight="bold")
    ax.text((RIGHT_SIZED_LO+RIGHT_SIZED_HI)/2, 1.07,
            "right-sized",
            fontsize=7, color="#005500", ha="center",
            style="italic", weight="bold")
    ax.text((RIGHT_SIZED_HI+TRANSITION_HI)/2, 1.06,
            "transition",
            fontsize=6.5, color="#7a5a00", ha="center",
            style="italic", weight="bold")
    ax.text((TRANSITION_HI+6.0)/2, 1.06,
            "over-\ncapacity",
            fontsize=6.5, color="#c55a11", ha="center",
            style="italic", weight="bold")

    # Errorbar plot of mean (line + markers + ribbons)
    cv = stds / np.maximum(means, 1e-9)  # coefficient of variation
    # Color points by CV: low CV = green, high CV = red
    cv_clipped = np.clip(cv, 0, 0.25) / 0.25
    point_colors = [(c, 1-c*0.6, 1-c) for c in cv_clipped]

    ax.errorbar(logp, means, yerr=stds, fmt="o-",
                color="#1f4e79", lw=2.0,
                ecolor="#1f4e79", elinewidth=1.0, capsize=4,
                markersize=8, markerfacecolor="#3a7ec0",
                markeredgecolor="#003d6b", markeredgewidth=0.7,
                zorder=10, label="mean$\\pm$std (3 seeds)")

    # Annotate each point with size label and AUC
    for i, lp in enumerate(logp):
        ax.annotate(f"{labels[i]}\n{means[i]:.3f}",
                    xy=(lp, means[i]),
                    xytext=(lp, means[i] - 0.10),
                    fontsize=6.5, ha="center", color="#003d6b",
                    weight="bold")

    # Ceilings
    ax.axhline(0.5, color="#a01700", lw=0.9, linestyle=":",
               label=r"Thm. 1 ceiling ($1/2$)")
    ax.axhline(0.574, color="#777777", lw=0.7, linestyle=":",
               label=r"fixed-feat ($0.574$)")
    ax.axhline(1.0, color="#0d4f4f", lw=0.5, linestyle=":")

    # Thm 3 corollary annotation
    ax.text(3.85, 0.59,
            "Thm. 3 corollary:\n"
            "min-sufficient capacity\n"
            "$\\in [10^3, 10^4]$ params",
            fontsize=6.5, color="#005500", ha="center",
            bbox=dict(boxstyle="round,pad=0.30",
                      facecolor="#e8f5f0", edgecolor="#2ca02c",
                      linewidth=0.6, alpha=0.92))

    ax.set_xlabel(r"$\log_{10}$(parameters)")
    ax.set_ylabel("AUC")
    ax.set_xlim(2.7, 6.0)
    ax.set_ylim(0.40, 1.12)
    ax.legend(loc="lower left", fontsize=6.5, ncol=1,
              framealpha=0.92)
    ax.grid(True, alpha=0.25, linestyle=":", axis="y")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_title("(b) U-curve with regime bands + CV annotations",
                 pad=4, fontsize=9, weight="bold")


def main():
    fig = plt.figure(figsize=(7.2, 4.0))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.05, 1.0],
                          wspace=0.18, left=0.04, right=0.99,
                          bottom=0.13, top=0.94)
    axA = fig.add_subplot(gs[0, 0], projection="3d")
    axB = fig.add_subplot(gs[0, 1])
    panel_A(axA)
    panel_B(axB)
    out_pdf = OUT / "fig19_v40_ucurve.pdf"
    out_png = OUT / "fig19_v40_ucurve.png"
    plt.savefig(out_pdf, dpi=300, bbox_inches="tight",
                pad_inches=0.05)
    plt.savefig(out_png, dpi=180, bbox_inches="tight",
                pad_inches=0.05)
    plt.close(fig)
    print(f"Wrote {out_pdf}")
    print(f"Wrote {out_png}")


if __name__ == "__main__":
    main()
