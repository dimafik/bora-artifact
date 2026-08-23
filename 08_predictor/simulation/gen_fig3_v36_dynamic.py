"""
gen_fig3_v36_dynamic.py — Dynamic 3D + 2D composite for Fig 3
(NE17 MLP vs Transformer capacity sweep).

Panel A (left, 3D): capacity-architecture-AUC ridge.
  X axis: log10(number of parameters), 10^3 to 10^6
  Y axis: architecture (MLP=0, Transformer=1)
  Z axis: AUC on PBFT moment-matched
  Two error-band ribbons (Transformer ridge + MLP slope) on a
  shaded background with translucent theorem ceilings (Thm.~1 at
  1/2, fixed-feature at 0.574).

Panel B (right, 2D): parameter efficiency bar chart.
  Capacity buckets × architecture; AUC-per-log-param efficiency.
  Highlights how the right-sized Transformer dominates MLP at
  every capacity scale.
"""
from __future__ import annotations
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap
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

# NE16 Transformer (3 seeds each)
TRF = [
    ("S1",   2273,   1.0000, 0.0000),
    ("S2",   17185,  0.9999, 0.0001),
    ("S3",   38065,  0.9991, 0.0013),
    ("S4",   100609, 0.8730, 0.1760),
    ("S5",   134081, 0.9865, 0.0180),
    ("S6",   299425, 0.8352, 0.1170),
]
# NE17 MLP (3 seeds each)
MLP = [
    ("M1", 577,    0.494, 0.020),
    ("M2", 5313,   0.495, 0.018),
    ("M3", 18817,  0.547, 0.025),
    ("M4", 70401,  0.590, 0.030),
    ("M5", 136193, 0.574, 0.090),
    ("M6", 534529, 0.883, 0.035),
]


def panel_A(ax):
    # 3D ridge plot
    trf_x = np.array([np.log10(r[1]) for r in TRF])
    trf_z = np.array([r[2] for r in TRF])
    trf_s = np.array([r[3] for r in TRF])
    mlp_x = np.array([np.log10(r[1]) for r in MLP])
    mlp_z = np.array([r[2] for r in MLP])
    mlp_s = np.array([r[3] for r in MLP])

    # Theorem 1 ceiling plane (z = 0.5) — translucent red mesh
    xg = np.linspace(2.7, 6.0, 12)
    yg = np.linspace(-0.25, 1.25, 6)
    Xg, Yg = np.meshgrid(xg, yg)
    Z_thm1 = np.full_like(Xg, 0.5)
    Z_fixed = np.full_like(Xg, 0.574)
    Z_perf = np.full_like(Xg, 1.0)
    # Layer the ceilings
    ax.plot_surface(Xg, Yg, Z_thm1, color="#ff6b3d", alpha=0.10,
                    rstride=1, cstride=1, linewidth=0,
                    antialiased=False, shade=False)
    ax.plot_surface(Xg, Yg, Z_fixed, color="#888888", alpha=0.08,
                    rstride=1, cstride=1, linewidth=0,
                    antialiased=False, shade=False)
    ax.plot_surface(Xg, Yg, Z_perf, color="#0d4f4f", alpha=0.06,
                    rstride=1, cstride=1, linewidth=0,
                    antialiased=False, shade=False)

    # Transformer ridge (y=1) — solid blue line with error ribbon
    y_trf = np.full_like(trf_x, 1.0)
    ax.plot(trf_x, y_trf, trf_z, color="#1f4e79", lw=2.4,
            marker="o", markersize=6, markerfacecolor="#3a7ec0",
            markeredgecolor="#1f4e79", label="Transformer (NE16)",
            zorder=10)
    # Error ribbon (Transformer)
    for xi, yi, zi, si in zip(trf_x, y_trf, trf_z, trf_s):
        ax.plot([xi, xi], [yi, yi], [zi-si, zi+si],
                color="#1f4e79", lw=1.0, alpha=0.7)

    # MLP slope (y=0) — solid red line with error ribbon
    y_mlp = np.full_like(mlp_x, 0.0)
    ax.plot(mlp_x, y_mlp, mlp_z, color="#a01700", lw=2.4,
            marker="s", markersize=6, markerfacecolor="#d65a3a",
            markeredgecolor="#a01700",
            label="MLP (NE17, this paper)", zorder=10)
    for xi, yi, zi, si in zip(mlp_x, y_mlp, mlp_z, mlp_s):
        ax.plot([xi, xi], [yi, yi], [zi-si, zi+si],
                color="#a01700", lw=1.0, alpha=0.7)

    # Shadow projections on the z=0.4 floor (drop lines)
    for xi, zi in zip(trf_x, trf_z):
        ax.plot([xi, xi], [1.0, 1.0], [0.4, zi],
                color="#1f4e79", lw=0.5, linestyle=":", alpha=0.4)
    for xi, zi in zip(mlp_x, mlp_z):
        ax.plot([xi, xi], [0.0, 0.0], [0.4, zi],
                color="#a01700", lw=0.5, linestyle=":", alpha=0.4)

    # Annotate theorem ceilings
    ax.text(5.95, -0.2, 0.52, "Thm. 1: $1/2$",
            color="#a01700", fontsize=6.5, ha="right", style="italic")
    ax.text(5.95, -0.2, 0.59, "fixed-feature: $0.574$",
            color="#555555", fontsize=6.5, ha="right", style="italic")
    ax.text(5.95, -0.2, 1.02, "perfect: $1.000$",
            color="#0d4f4f", fontsize=6.5, ha="right", style="italic")

    # Highlight right-sized regime band on the floor
    rs_x_lo, rs_x_hi = np.log10(2e3), np.log10(5e4)
    floor_pts = [(rs_x_lo, 0.85, 0.4), (rs_x_hi, 0.85, 0.4),
                 (rs_x_hi, 1.15, 0.4), (rs_x_lo, 1.15, 0.4)]
    floor_xs = [p[0] for p in floor_pts] + [floor_pts[0][0]]
    floor_ys = [p[1] for p in floor_pts] + [floor_pts[0][1]]
    floor_zs = [p[2] for p in floor_pts] + [floor_pts[0][2]]
    ax.plot(floor_xs, floor_ys, floor_zs, color="#00d4aa", lw=1.4)
    ax.text(np.log10(1e4), 1.0, 0.42, "right-sized regime",
            color="#00d4aa", fontsize=6.5, ha="center",
            weight="bold")

    ax.set_xlabel(r"$\log_{10}$(parameters)", labelpad=2)
    ax.set_ylabel("Architecture", labelpad=-4)
    ax.set_zlabel("AUC", labelpad=-2)
    ax.set_yticks([0.0, 1.0])
    ax.set_yticklabels(["MLP", "TRF"], fontsize=7)
    ax.set_zlim(0.4, 1.05)
    ax.set_xlim(2.7, 6.0)
    ax.view_init(elev=22, azim=-62)
    ax.tick_params(axis="x", pad=-2)
    ax.tick_params(axis="y", pad=-2)
    ax.tick_params(axis="z", pad=-1)
    ax.xaxis.pane.set_facecolor("#f8f8fc")
    ax.yaxis.pane.set_facecolor("#f8f8fc")
    ax.zaxis.pane.set_facecolor("#ffffff")
    ax.xaxis.pane.set_edgecolor("#cccccc")
    ax.yaxis.pane.set_edgecolor("#cccccc")
    ax.zaxis.pane.set_edgecolor("#cccccc")
    ax.grid(True, linestyle=":", alpha=0.25)
    ax.set_title("(a) 3-D capacity-architecture-AUC ridge",
                 pad=4, fontsize=9, weight="bold")


def panel_B(ax):
    # AUC bar comparison at matched capacity bins
    bins = ["$\\sim$2K", "$\\sim$17K", "$\\sim$70K", "$\\sim$135K",
            "$\\sim$500K"]
    trf_y = [TRF[0][2], TRF[1][2], TRF[3][2], TRF[4][2], TRF[5][2]]
    mlp_y = [MLP[0][2], MLP[2][2], MLP[3][2], MLP[4][2], MLP[5][2]]
    trf_e = [TRF[0][3], TRF[1][3], TRF[3][3], TRF[4][3], TRF[5][3]]
    mlp_e = [MLP[0][3], MLP[2][3], MLP[3][3], MLP[4][3], MLP[5][3]]

    x = np.arange(len(bins))
    w = 0.38

    # Gradient backgrounds for bar heights
    bars_trf = ax.bar(x - w/2, trf_y, w, yerr=trf_e,
                      color="#3a7ec0", edgecolor="#1f4e79",
                      linewidth=0.8, capsize=3, label="Transformer",
                      error_kw=dict(ecolor="#1f4e79", lw=0.8))
    bars_mlp = ax.bar(x + w/2, mlp_y, w, yerr=mlp_e,
                      color="#d65a3a", edgecolor="#a01700",
                      linewidth=0.8, capsize=3, label="MLP",
                      error_kw=dict(ecolor="#a01700", lw=0.8))

    # Gap annotations
    for xi, ty, my in zip(x, trf_y, mlp_y):
        gap = ty - my
        ax.annotate(f"$\\Delta{{=}}{gap:+.2f}$",
                    xy=(xi, max(ty, my) + 0.04),
                    fontsize=6.5, ha="center",
                    color="#00d4aa", weight="bold")

    # Theorem ceilings
    ax.axhline(0.5, color="#a01700", lw=0.8, linestyle=":",
               label="Thm. 1 ($1/2$)")
    ax.axhline(0.574, color="#555555", lw=0.8, linestyle=":",
               label="fixed-feature ($0.574$)")
    ax.axhline(1.0, color="#0d4f4f", lw=0.6, linestyle=":")

    ax.set_xticks(x)
    ax.set_xticklabels(bins, fontsize=7.5)
    ax.set_xlabel("Capacity bucket (parameters)")
    ax.set_ylabel("AUC (3 seeds, mean$\\pm$std)")
    ax.set_ylim(0.4, 1.18)
    ax.legend(loc="upper center", ncol=4, fontsize=6.5,
              framealpha=0.9, bbox_to_anchor=(0.5, 1.15))
    ax.grid(True, alpha=0.25, linestyle=":", axis="y")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_title("(b) Per-capacity head-to-head with gap annotations",
                 pad=4, fontsize=9, weight="bold")


def main():
    fig = plt.figure(figsize=(7.2, 4.0))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.15, 1.0],
                          wspace=0.18, left=0.02, right=0.98,
                          bottom=0.12, top=0.92)
    axA = fig.add_subplot(gs[0, 0], projection="3d")
    axB = fig.add_subplot(gs[0, 1])
    panel_A(axA)
    panel_B(axB)
    out_pdf = OUT / "fig16_v36_mlp_vs_transformer.pdf"
    out_png = OUT / "fig16_v36_mlp_vs_transformer.png"
    plt.savefig(out_pdf, dpi=300, bbox_inches="tight",
                pad_inches=0.05)
    plt.savefig(out_png, dpi=180, bbox_inches="tight",
                pad_inches=0.05)
    plt.close(fig)
    print(f"Wrote {out_pdf}")
    print(f"Wrote {out_png}")


if __name__ == "__main__":
    main()
