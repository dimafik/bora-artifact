"""
gen_fig8_v41_pgd.py - NE11 PGD adversarial robustness landscape
across detector classes on PBFT moment-matched.

Panel A (left, 3D): epsilon x detector x AUC bar landscape with
Theorem 1 (1/2) and Theorem 7 (1/2 + C * delta^{3/2}) ceilings
as translucent planes. Linear scorer saturates at the T7 ceiling
because moment residuals stay ~6.4e-4 regardless of epsilon;
the Transformer plateau at AUC=0.821 is the robust zone.

Panel B (right, 2D): epsilon vs AUC dual-axis plot.
  Primary y: detector AUC (Linear, Static-feature, Transformer)
  Secondary y: PGD moment residuals (delta_mean, delta_var)
  Annotation: "PGD saturates because moment residual is
  independent of epsilon" - Transformer invariant to attack
  budget.
"""
from __future__ import annotations
import numpy as np
import matplotlib.pyplot as plt
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

# NE11 measurements
EPSILONS = np.array([0.05, 0.10, 0.20])
DETECTORS = ["Linear", "Static-feat", "TinyTRF"]
DET_COLORS = ["#d62728", "#9467bd", "#2ca02c"]
# AUC matrix [detector_idx][epsilon_idx]
AUC = np.array([
    [0.500, 0.500, 0.500],  # Linear (T1 ceiling)
    [0.534, 0.534, 0.534],  # Static fixed-feature
    [0.821, 0.821, 0.821],  # TinyTransformer
])
DELTA_MEAN_RES = np.array([0.0, 0.0, 0.0])
DELTA_VAR_RES = np.array([6.4e-4, 6.4e-4, 6.4e-4])

# T7 ceiling for Linear under delta-slack:
# AUC <= 1/2 + C * delta^{3/2}, where delta = sqrt(var) approx
# For C=3.5, delta=sqrt(6.4e-4)=0.0253:
# 1/2 + 3.5 * 0.0253^{1.5} = 0.5 + 3.5 * 0.00403 = 0.514
T7_CEILING = 0.5 + 3.5 * (np.sqrt(DELTA_VAR_RES[0])) ** 1.5


def panel_A(ax):
    n_eps = len(EPSILONS)
    n_det = len(DETECTORS)
    eps_idx = np.arange(n_eps)
    det_idx = np.arange(n_det)
    X, Y = np.meshgrid(eps_idx, det_idx, indexing="ij")
    X = X.flatten()
    Y = Y.flatten()
    Z = np.zeros_like(X, dtype=float)
    DZ = AUC.T.flatten()  # shape (n_eps * n_det)
    # Colors per detector
    bar_colors = []
    for ei in range(n_eps):
        for dj in range(n_det):
            bar_colors.append(DET_COLORS[dj])

    # T1 ceiling plane
    xg = np.linspace(-0.3, n_eps - 0.3, 8)
    yg = np.linspace(-0.3, n_det - 0.3, 6)
    XG, YG = np.meshgrid(xg, yg)
    Z_thm1 = np.full_like(XG, 0.5)
    Z_t7 = np.full_like(XG, T7_CEILING)
    Z_perf = np.full_like(XG, 1.0)
    ax.plot_surface(XG, YG, Z_thm1, color="#ff6b3d", alpha=0.13,
                    rstride=1, cstride=1, linewidth=0,
                    antialiased=False, shade=False)
    ax.plot_surface(XG, YG, Z_t7, color="#777777", alpha=0.10,
                    rstride=1, cstride=1, linewidth=0,
                    antialiased=False, shade=False)
    ax.plot_surface(XG, YG, Z_perf, color="#0d4f4f", alpha=0.05,
                    rstride=1, cstride=1, linewidth=0,
                    antialiased=False, shade=False)

    # Bars
    bar_w, bar_d = 0.45, 0.45
    ax.bar3d(X - bar_w/2, Y - bar_d/2, Z, bar_w, bar_d, DZ,
             color=bar_colors, edgecolor="#222222", linewidth=0.4,
             alpha=0.92, shade=True, zsort="average")

    # Robust zone (Transformer plateau) annotation
    ax.text(1.0, n_det - 0.5, 0.87, "robust plateau",
            color="#005500", fontsize=7, ha="center",
            style="italic", weight="bold")
    ax.text(2.4, -0.7, 0.52, "Thm. 1 ($1/2$)",
            color="#a01700", fontsize=6.5, ha="right",
            style="italic")
    ax.text(2.4, -0.7, T7_CEILING + 0.02,
            f"Thm. 7 ($\\leq {T7_CEILING:.3f}$)",
            color="#444444", fontsize=6.5, ha="right",
            style="italic")

    ax.set_xticks(eps_idx)
    ax.set_xticklabels([f"$\\varepsilon{{=}}{e:g}$" for e in EPSILONS],
                       fontsize=7, weight="bold")
    ax.set_yticks(det_idx)
    ax.set_yticklabels(DETECTORS, fontsize=7)
    ax.set_xlabel("PGD attack budget", labelpad=2)
    ax.set_ylabel("Detector", labelpad=-2)
    ax.set_zlabel("AUC", labelpad=-2)
    ax.set_zlim(0.0, 1.05)
    ax.view_init(elev=22, azim=-58)
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
    ax.set_title(r"(a) 3-D PGD landscape: $\varepsilon \times$ detector $\times$ AUC",
                 pad=4, fontsize=9, weight="bold")


def panel_B(ax):
    # Primary axis: AUC vs epsilon for 3 detectors
    eps = EPSILONS
    # Plot AUC lines per detector
    for di, (name, color) in enumerate(zip(DETECTORS, DET_COLORS)):
        marker = ["s", "D", "*"][di]
        size = [60, 60, 180][di]
        ax.plot(eps, AUC[di], lw=2.0, color=color, alpha=0.9,
                zorder=10)
        ax.scatter(eps, AUC[di], s=size, marker=marker,
                   color=color, edgecolor="black", linewidth=0.7,
                   zorder=11, label=name)
        # Value label at end
        ax.text(eps[-1] + 0.01, AUC[di, -1],
                f"{AUC[di, -1]:.3f}",
                color=color, fontsize=7, weight="bold",
                va="center")

    # Theorem ceilings
    ax.axhline(0.5, color="#a01700", lw=0.9, linestyle=":",
               label=r"Thm. 1 ($1/2$)")
    ax.axhline(T7_CEILING, color="#555555", lw=0.7,
               linestyle=":",
               label=f"Thm. 7 ($\\leq {T7_CEILING:.3f}$)")
    ax.axhline(1.0, color="#0d4f4f", lw=0.5, linestyle=":")

    # Robust zone shading
    ax.axhspan(0.7, 1.0, color="#c8e6c9", alpha=0.20, zorder=0)
    ax.text(0.025, 0.97, "robust zone (TinyTRF plateau)",
            fontsize=6.5, color="#005500", style="italic",
            weight="bold", ha="left", va="top")

    # Secondary y-axis: moment residual
    ax2 = ax.twinx()
    ax2.plot(eps, DELTA_VAR_RES, "o--", color="#7a5a00",
             markersize=5, lw=1.2,
             label=r"$|\Delta\sigma^2| \approx 6.4{\times}10^{-4}$")
    ax2.plot(eps, DELTA_MEAN_RES + 1e-9, "v--", color="#5a2e7e",
             markersize=5, lw=1.2,
             label=r"$|\Delta\mu| \approx 0$")
    ax2.set_yscale("log")
    ax2.set_ylim(1e-10, 1e-1)
    ax2.set_ylabel(r"PGD moment residual (log)",
                   color="#7a5a00", fontsize=7.5)
    ax2.tick_params(axis="y", colors="#7a5a00", labelsize=6.5)

    # Annotation explaining saturation
    ax.text(0.125, 0.27,
            "PGD saturates:\nresidual independent of $\\varepsilon$\n"
            r"$\Rightarrow$ AUC $\perp\!\!\!\perp \varepsilon$",
            fontsize=6.5, color="#444444", ha="center",
            bbox=dict(boxstyle="round,pad=0.30",
                      facecolor="#f0f0f7",
                      edgecolor="#5050aa", linewidth=0.6,
                      alpha=0.90))

    # Cosmetics
    ax.set_xlim(0.02, 0.235)
    ax.set_ylim(0.0, 1.05)
    ax.set_xticks(eps)
    ax.set_xticklabels([f"{e:g}" for e in eps], fontsize=7.5,
                        weight="bold")
    ax.set_xlabel(r"PGD attack budget $\varepsilon$")
    ax.set_ylabel("AUC")
    ax.legend(loc="center right", fontsize=6.5, ncol=1,
              framealpha=0.90)
    ax2.legend(loc="lower right", fontsize=6.5, framealpha=0.90)
    ax.grid(True, alpha=0.25, linestyle=":", axis="y")
    ax.spines["top"].set_visible(False)
    ax.set_title("(b) Detector AUC + PGD moment residual",
                 pad=4, fontsize=9, weight="bold")


def main():
    fig = plt.figure(figsize=(7.2, 4.0))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.05, 1.05],
                          wspace=0.22, left=0.04, right=0.94,
                          bottom=0.14, top=0.88)
    axA = fig.add_subplot(gs[0, 0], projection="3d")
    axB = fig.add_subplot(gs[0, 1])
    panel_A(axA)
    panel_B(axB)
    fig.suptitle(
        r"NE11 PGD adversarial robustness: TinyTransformer retains AUC $= 0.821$ across $\varepsilon \in \{0.05, 0.10, 0.20\}$",
        fontsize=9.5, y=0.97, weight="bold")
    out_pdf = OUT / "fig20_v41_pgd.pdf"
    out_png = OUT / "fig20_v41_pgd.png"
    plt.savefig(out_pdf, dpi=300, bbox_inches="tight",
                pad_inches=0.05)
    plt.savefig(out_png, dpi=180, bbox_inches="tight",
                pad_inches=0.05)
    plt.close(fig)
    print(f"Wrote {out_pdf}")
    print(f"Wrote {out_png}")


if __name__ == "__main__":
    main()
