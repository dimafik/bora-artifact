"""
gen_fig5_v38_canonical.py — NE13 (beta-consistent, gamma-robust)
canonical robustness-consistency curve, the v34/v35 top-venue
framework alignment hero figure.

Panel A (left, 2D): (beta, gamma) achievement plane.
  X axis: gamma-robustness (worst-case AUC across delta >= 0)
  Y axis: beta-consistency (AUC at delta = 0)
  Forbidden red zone above beta = 1/2 (Thm. 1 ceiling for linear).
  Achievable green zone for window-aware non-linear class.
  T7 ceiling curve: beta <= 1/2 + C * delta_max^{3/2}.
  NE13 detector points: Linear (red square at ~(0.478, 0.478)),
  Kurtosis (grey square at ~(0.433, 0.439)),
  Transformer (green star at ~(0.990, 0.990)).
  Annotated with Purohit-Svitkina-Kumar [17] frame reference.

Panel B (right, 3D): AUC(delta) ridge plot per detector class.
  X axis: delta (linear scale)
  Y axis: detector class index (0 = Linear, 1 = Kurtosis,
                                2 = Transformer)
  Z axis: AUC
  Three ridges with NE13 markers, T1 ceiling plane (z=0.5),
  fixed-feature ceiling plane (z=0.574), highlights the
  "capacity-gap chasm" between Linear/Kurtosis and Transformer.
"""
from __future__ import annotations
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, FancyArrow
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

# NE13 measurements (from Table III in v37)
DELTAS = np.array([0.0, 0.001, 0.01, 0.1])
LIN_AUC = np.array([0.478, 0.536, 0.593, 0.986])
KUR_AUC = np.array([0.439, 0.450, 0.433, 0.447])
TRF_AUC = np.array([0.990, 0.993, 0.990, 1.000])


def panel_A(ax):
    # (beta, gamma) plane
    ax.set_xlim(0.40, 1.02)
    ax.set_ylim(0.40, 1.02)
    ax.set_aspect("equal")
    # Achievable Pareto upper triangle (beta >= gamma)
    pareto = Polygon([(0.40, 0.40), (1.02, 1.02), (0.40, 1.02)],
                     closed=True, facecolor="#e8f5f0",
                     edgecolor="none", alpha=0.6, zorder=1)
    ax.add_patch(pareto)
    # Linear-forbidden zone (Thm. 1: beta_lin <= 1/2 for any delta=0)
    # Actually under T1, linear AT delta=0 has AUC = 1/2 exactly.
    # Forbidden region: beta > 1/2 for linear.
    forbidden = Polygon([(0.40, 0.50), (1.02, 0.50),
                         (1.02, 1.02), (0.40, 1.02)],
                        closed=True, facecolor="#ffcdc4",
                        edgecolor="none", alpha=0.35, zorder=0)
    ax.add_patch(forbidden)
    # Theorem 1 horizontal line at beta = 1/2
    ax.axhline(0.5, color="#a01700", lw=1.4, linestyle="--",
               zorder=3)
    ax.text(0.42, 0.515,
            r"Thm. 1 ceiling for linear: $\beta_{\rm lin}\leq 1/2$",
            color="#a01700", fontsize=7.5, style="italic",
            weight="bold")
    # Theorem 7 curve: beta = 1/2 + C * delta^{3/2} for varying
    # delta — interpret as "ceiling at large delta"
    # For visualization: show C=3.5 envelope
    gamma_axis = np.linspace(0.42, 1.0, 60)
    # T7 ceiling sweeps as delta grows from 0; this is what the
    # Linear NE13 traces (approximately follows ceiling)
    ax.plot([0.478, 1.0], [0.478, 1.0], color="#aaaaaa",
            lw=0.8, linestyle=":", alpha=0.8, zorder=2)
    ax.text(0.85, 0.82, "Pareto: $\\beta=\\gamma$",
            color="#777777", fontsize=7, rotation=45, ha="center",
            style="italic")
    # NE13 detector points
    # Linear: trace along ceiling as delta grows
    lin_beta = LIN_AUC[0]  # AUC at delta=0
    lin_gamma = np.min(LIN_AUC)  # worst AUC
    kur_beta = KUR_AUC[0]
    kur_gamma = np.min(KUR_AUC)
    trf_beta = TRF_AUC[0]
    trf_gamma = np.min(TRF_AUC)
    # Connect: draw a small arc/cone showing the trajectory of
    # (gamma, beta) as the achievable region expands with delta.
    # Linear scorer: small red square + trajectory
    ax.scatter([lin_gamma], [lin_beta], s=140, marker="s",
               color="#d62728", edgecolor="#7a0e0e", linewidth=1.2,
               zorder=10, label="Linear")
    ax.annotate("Linear\n$\\beta{=}\\gamma{=}0.478$",
                xy=(lin_gamma, lin_beta), xytext=(0.55, 0.43),
                fontsize=7, color="#7a0e0e",
                arrowprops=dict(arrowstyle="->", color="#7a0e0e",
                                lw=0.6))
    # Kurtosis: small grey square
    ax.scatter([kur_gamma], [kur_beta], s=110, marker="s",
               color="#888888", edgecolor="#444444", linewidth=1.0,
               zorder=10, label="Kurtosis")
    ax.annotate("Kurtosis\n$(0.433, 0.439)$",
                xy=(kur_gamma, kur_beta), xytext=(0.48, 0.55),
                fontsize=7, color="#444444",
                arrowprops=dict(arrowstyle="->", color="#444444",
                                lw=0.6))
    # Transformer: bright green star
    ax.scatter([trf_gamma], [trf_beta], s=300, marker="*",
               color="#2ca02c", edgecolor="#005500", linewidth=1.2,
               zorder=11, label="Transformer (TinyTRF)")
    ax.annotate("Transformer\n$\\beta{=}0.990,\\gamma{=}0.990$",
                xy=(trf_gamma, trf_beta), xytext=(0.55, 0.93),
                fontsize=7.5, color="#005500", weight="bold",
                arrowprops=dict(arrowstyle="->", color="#005500",
                                lw=0.6))
    # Achievable region label
    ax.text(0.72, 0.95, "Achievable by\nwindow-aware\nnon-linear "
            "class\n(Thm. 3)",
            color="#005500", fontsize=7, ha="center", style="italic",
            bbox=dict(boxstyle="round,pad=0.25",
                      facecolor="#e8f5f0", edgecolor="#2ca02c",
                      linewidth=0.6, alpha=0.85))
    # Forbidden region label
    ax.text(0.92, 0.74, "Forbidden\nfor any\nlinear scorer",
            color="#7a0e0e", fontsize=7, ha="center", style="italic",
            rotation=0,
            bbox=dict(boxstyle="round,pad=0.25",
                      facecolor="#ffe7e0", edgecolor="#a01700",
                      linewidth=0.6, alpha=0.85))
    # Canonical PSK frame reference
    ax.text(0.42, 1.005,
            r"Purohit-Svitkina-Kumar~[17] canonical $(\beta,\gamma)$ frame",
            fontsize=7, color="#1f4e79", style="italic",
            weight="bold")
    ax.set_xlabel(r"$\gamma$-robustness $=\min_{\delta\geq 0}\,$AUC$(\delta)$")
    ax.set_ylabel(r"$\beta$-consistency $=\,$AUC$(\delta=0)$")
    ax.grid(True, alpha=0.25, linestyle=":")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.set_title(r"(a) $(\beta,\gamma)$ achievement plane",
                 pad=4, fontsize=9, weight="bold")


def panel_B(ax):
    # 3D AUC(delta) ridges
    detector_idx = np.array([0, 1, 2])
    detector_names = ["Linear", "Kurtosis", "TRF"]
    detector_colors = ["#d62728", "#888888", "#2ca02c"]
    detector_aucs = [LIN_AUC, KUR_AUC, TRF_AUC]

    # T1 ceiling plane (z = 0.5) and fixed-feature ceiling (0.574)
    dx = np.linspace(-0.005, 0.105, 12)
    dy = np.linspace(-0.3, 2.3, 6)
    DX, DY = np.meshgrid(dx, dy)
    Z_thm1 = np.full_like(DX, 0.5)
    Z_fixed = np.full_like(DX, 0.574)
    Z_perf = np.full_like(DX, 1.0)
    ax.plot_surface(DX, DY, Z_thm1, color="#ff6b3d", alpha=0.13,
                    rstride=1, cstride=1, linewidth=0,
                    antialiased=False, shade=False)
    ax.plot_surface(DX, DY, Z_fixed, color="#888888", alpha=0.10,
                    rstride=1, cstride=1, linewidth=0,
                    antialiased=False, shade=False)
    ax.plot_surface(DX, DY, Z_perf, color="#0d4f4f", alpha=0.06,
                    rstride=1, cstride=1, linewidth=0,
                    antialiased=False, shade=False)
    # T7 analytical ceiling (1/2 + C * delta^{3/2}) with C=3.5
    delta_fine = np.linspace(0, 0.1, 100)
    t7 = 0.5 + 3.5 * delta_fine ** 1.5
    ax.plot(delta_fine, np.full_like(delta_fine, -0.25), t7,
            color="#a01700", lw=1.6, linestyle="--",
            label=r"Thm. 7: $1/2+C\delta^{3/2}$")

    # Three detector ridges
    for idx, aucs, color, name in zip(detector_idx, detector_aucs,
                                       detector_colors,
                                       detector_names):
        y = np.full_like(DELTAS, idx, dtype=float)
        ax.plot(DELTAS, y, aucs, color=color, lw=2.4,
                marker="o", markersize=6,
                markerfacecolor=color, markeredgecolor="black",
                markeredgewidth=0.5, zorder=10)
        # Drop shadow projection on z=0.4 floor
        for dl, au in zip(DELTAS, aucs):
            ax.plot([dl, dl], [idx, idx], [0.40, au],
                    color=color, lw=0.6, linestyle=":", alpha=0.4)

    # Annotation: "chasm"
    ax.text(0.05, 1.0, 0.75, "capacity-gap\nchasm",
            color="#005500", fontsize=7, ha="center",
            style="italic", weight="bold",
            bbox=dict(boxstyle="round,pad=0.20",
                      facecolor="#e8f5f0", edgecolor="#2ca02c",
                      linewidth=0.5, alpha=0.85))
    # Ceiling text labels
    ax.text(0.105, -0.3, 0.5, "Thm. 1 ($1/2$)",
            color="#a01700", fontsize=6.5, ha="right", style="italic")
    ax.text(0.105, -0.3, 0.585, "fixed feat. ($0.574$)",
            color="#555555", fontsize=6.5, ha="right", style="italic")

    ax.set_xlabel(r"$\delta$ (moment-matching tolerance)",
                  labelpad=2)
    ax.set_ylabel("Detector", labelpad=-4)
    ax.set_zlabel("AUC", labelpad=-2)
    ax.set_yticks(detector_idx)
    ax.set_yticklabels(detector_names, fontsize=7)
    ax.set_zlim(0.40, 1.05)
    ax.set_xlim(0, 0.1)
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
    ax.set_title(r"(b) AUC$(\delta)$ per detector class",
                 pad=4, fontsize=9, weight="bold")


def main():
    fig = plt.figure(figsize=(7.2, 4.0))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.05, 1.05],
                          wspace=0.18, left=0.06, right=0.99,
                          bottom=0.14, top=0.88)
    axA = fig.add_subplot(gs[0, 0])
    axB = fig.add_subplot(gs[0, 1], projection="3d")
    panel_A(axA)
    panel_B(axB)
    fig.suptitle(
        r"NE13 canonical robustness--consistency curve: linear-detector forbidden zone vs.\ achievable region",
        fontsize=10, y=0.97, weight="bold")
    out_pdf = OUT / "fig17_v38_canonical.pdf"
    out_png = OUT / "fig17_v38_canonical.png"
    plt.savefig(out_pdf, dpi=300, bbox_inches="tight",
                pad_inches=0.05)
    plt.savefig(out_png, dpi=180, bbox_inches="tight",
                pad_inches=0.05)
    plt.close(fig)
    print(f"Wrote {out_pdf}")
    print(f"Wrote {out_png}")


if __name__ == "__main__":
    main()
