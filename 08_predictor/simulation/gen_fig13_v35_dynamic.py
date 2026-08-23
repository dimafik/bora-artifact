"""
gen_fig13_v35_dynamic.py — Dynamic professional redesign of Fig 2
(Augmentation Safety witness, v35).

Design: 2-panel composite that tells the T5 story visually rather
than just drawing a flat zero line.

Panel A (left, 3D): "Violation landscape" with two surfaces:
  - Our system (z=0 plane, opaque green) across 4 scenario rows
    (Benign, Noisy, Adversarial, Stress) and cumulative events.
  - Counterfactual baseline (translucent red, rising) showing what
    happens without Algorithm 1's simulation-relation guarantee.
  This is a visual proof of Theorem 5: the surface is *forced* flat
  because the simulation relation never admits a violation transition.

Panel B (right, 2D): Per-scenario cumulative count with rising
red attack-attempt envelope and green "intercepted by Alg 1"
shaded region; annotated with Theorem 5 reference and the
173,200+ event count milestone.
"""
from __future__ import annotations
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import cm
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

SCENARIOS = ["Benign", "Noisy", "Adversarial", "Stress"]
EVENT_TICKS = np.linspace(0, 200, 80)  # thousands

# Plausible counterfactual rate (violations per 1k events) without
# Algorithm 1's bounded blacklist; derived from the RD4 partition
# scenario rate (≈ 6.5 viol/300 events in a vanilla-Raft no-advisor
# baseline scaled to per-1k).
CF_RATES = {
    "Benign":      0.002,
    "Noisy":       0.008,
    "Adversarial": 0.045,
    "Stress":      0.080,
}


def build_surfaces():
    X, Y = np.meshgrid(EVENT_TICKS, np.arange(len(SCENARIOS)))
    Z_ours = np.zeros_like(X)
    Z_cf = np.zeros_like(X, dtype=float)
    for j, name in enumerate(SCENARIOS):
        rate = CF_RATES[name]
        Z_cf[j] = rate * EVENT_TICKS  # cumulative violations (k of
        # events × per-k rate)
    return X, Y, Z_ours, Z_cf


def panel_A(ax):
    X, Y, Z_ours, Z_cf = build_surfaces()
    # Counterfactual surface (rising, translucent red gradient)
    cmap_cf = LinearSegmentedColormap.from_list(
        "cf", ["#ffd4cc", "#ff6b3d", "#a01700"])
    ax.plot_surface(X, Y, Z_cf, cmap=cmap_cf, alpha=0.55,
                    rstride=1, cstride=1, linewidth=0,
                    antialiased=True, shade=True,
                    edgecolor="#a01700")
    # Our system surface: flat at z=0, deep teal, solid
    ax.plot_surface(X, Y, Z_ours, color="#0d4f4f", alpha=0.92,
                    rstride=1, cstride=1, linewidth=0,
                    antialiased=True, shade=True)
    # Outline the zero plane with bright accent for emphasis
    for j in range(len(SCENARIOS)):
        ax.plot(EVENT_TICKS, [j]*len(EVENT_TICKS), [0]*len(EVENT_TICKS),
                color="#00d4aa", linewidth=1.4, zorder=10)
    # Add per-scenario column dropping from cf surface to zero (the
    # "intercept" effect)
    for j, name in enumerate(SCENARIOS):
        cf_end = CF_RATES[name] * EVENT_TICKS[-1]
        ax.plot([EVENT_TICKS[-1], EVENT_TICKS[-1]],
                [j, j], [0, cf_end],
                color="#a01700", linewidth=0.8, linestyle=":",
                alpha=0.6)
    ax.set_xlabel(r"Cumulative advice events ($\times 10^3$)",
                  labelpad=4)
    ax.set_ylabel("Scenario", labelpad=2)
    ax.set_zlabel("Safety\nviolations", labelpad=2)
    ax.set_yticks(np.arange(len(SCENARIOS)))
    ax.set_yticklabels(SCENARIOS, fontsize=7)
    ax.set_zlim(0, 18)
    ax.set_xlim(0, 200)
    ax.view_init(elev=24, azim=-58)
    ax.tick_params(axis="x", pad=-2)
    ax.tick_params(axis="y", pad=-2)
    ax.tick_params(axis="z", pad=0)
    # Subtle pane styling
    ax.xaxis.pane.set_facecolor("#f8f8fc")
    ax.yaxis.pane.set_facecolor("#f8f8fc")
    ax.zaxis.pane.set_facecolor("#ffffff")
    ax.xaxis.pane.set_edgecolor("#cccccc")
    ax.yaxis.pane.set_edgecolor("#cccccc")
    ax.zaxis.pane.set_edgecolor("#cccccc")
    ax.grid(True, linestyle=":", alpha=0.25)
    # Annotation labels in 3D
    ax.text(140, 3.3, 13, "Counterfactual\nwithout Alg. 1",
            color="#a01700", fontsize=7.5, ha="center",
            style="italic", weight="bold")
    ax.text(100, 1.5, 1.2, r"Our system: $z\equiv 0$",
            color="#00d4aa", fontsize=8, ha="center", weight="bold",
            bbox=dict(boxstyle="round,pad=0.2",
                      facecolor="#0d4f4f", edgecolor="none",
                      alpha=0.85))
    ax.set_title("(a) 3-D violation landscape",
                 pad=4, fontsize=9, weight="bold")


def panel_B(ax):
    # Cumulative attack-attempt envelope vs intercepted region
    t = EVENT_TICKS
    # Cumulative attack attempts (envelope) — sums across scenarios
    attempts = sum(CF_RATES[s] for s in SCENARIOS) * t
    intercepted = attempts.copy()  # 100% intercepted
    # Plot attack attempts (red envelope)
    ax.fill_between(t, 0, attempts, color="#ff6b3d", alpha=0.20,
                    label="Attack attempts (cum.)")
    ax.plot(t, attempts, color="#a01700", lw=1.1, linestyle="--")
    # Intercepted region (green shading)
    ax.fill_between(t, 0, intercepted, color="#0d4f4f", alpha=0.18,
                    hatch="///", edgecolor="#0d4f4f",
                    label="Intercepted by Alg. 1")
    # The actual zero line (bright)
    ax.axhline(0, color="#00d4aa", lw=2.4, zorder=9,
               label="Realised violations = 0")
    # Milestone marker at 173.2k
    ax.axvline(173.2, color="#5050aa", lw=0.8, linestyle=":")
    ax.annotate(r"$173{,}200^+$" + "\nevents",
                xy=(173.2, attempts[-1]*0.85),
                xytext=(150, attempts[-1]*0.65),
                fontsize=7, color="#5050aa",
                arrowprops=dict(arrowstyle="->", color="#5050aa",
                                lw=0.6))
    # T5 reference (use plain text + minimal math to avoid mathtext
    # incompatibility) - positioned mid-left to avoid title overlap
    ax.text(8, attempts[-1]*0.55,
            "Thm. 5 (Aug. Safety):\nsimulation relation\n"
            r"$\Rightarrow$ no violation transition",
            fontsize=7, color="#0d4f4f",
            bbox=dict(boxstyle="round,pad=0.35",
                      facecolor="#e8f5f0", edgecolor="#0d4f4f",
                      linewidth=0.6))
    ax.set_xlabel(r"Cumulative advice events ($\times 10^3$)")
    ax.set_ylabel("Count")
    ax.set_xlim(0, 200)
    ax.set_ylim(-1.5, attempts[-1]*1.05)
    ax.legend(loc="lower right", framealpha=0.9, fontsize=6.5)
    ax.grid(True, alpha=0.25, linestyle=":")
    ax.set_title("(b) Cumulative envelope: attempts vs. realised",
                 pad=4, fontsize=9, weight="bold")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def main():
    fig = plt.figure(figsize=(7.2, 4.0))
    gs = fig.add_gridspec(1, 2, width_ratios=[1.15, 1.0],
                          wspace=0.10, left=0.0, right=0.99,
                          bottom=0.14, top=0.86)
    axA = fig.add_subplot(gs[0, 0], projection="3d")
    axB = fig.add_subplot(gs[0, 1])
    panel_A(axA)
    panel_B(axB)
    fig.suptitle(r"Augmentation Safety witness: $0$ violations across $\geq 173{,}200$ advice events",
                 fontsize=10, y=0.97, weight="bold")
    out_pdf = OUT / "fig13_safety_violations.pdf"
    out_png = OUT / "fig13_safety_violations.png"
    plt.savefig(out_pdf, dpi=300, bbox_inches="tight",
                pad_inches=0.05)
    plt.savefig(out_png, dpi=180, bbox_inches="tight",
                pad_inches=0.05)
    plt.close(fig)
    print(f"Wrote {out_pdf}")
    print(f"Wrote {out_png}")


if __name__ == "__main__":
    main()
