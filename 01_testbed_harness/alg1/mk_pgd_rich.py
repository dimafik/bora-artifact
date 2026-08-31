# RETRACTED NUMBERS.  The AUC series 0.774/0.748/0.733/0.819 hardcoded below
# is the figure Section V-F now retracts: it came from a single restart
# initialised at autocorrelation 0.85.  Kept for provenance only.
# Do not re-run to produce a figure; see recreate_fig_pgd_corrected.py.
# Rich regeneration of Fig.7 (White-box adaptive adversary) from REAL data in
# mm_adaptive_results.txt. Produces a complex 2D (2-panel) and a 3D version.
# No interpolation / no fabricated points -- only the measured operating points.
# Style: muted academic palette + Arial, matches the paper's other figures.
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import rcParams
from matplotlib.patches import FancyBboxPatch
from matplotlib.lines import Line2D
from mpl_toolkits.mplot3d import Axes3D  # noqa: F401
from matplotlib import cm
from matplotlib.colors import Normalize, LinearSegmentedColormap

rcParams["font.family"] = "Arial"
rcParams["pdf.fonttype"] = 42
rcParams["ps.fonttype"] = 42
rcParams["axes.linewidth"] = 0.8
rcParams["font.size"] = 8
rcParams["mathtext.fontset"] = "dejavusans"

NAVY = "#25405c"; BURG = "#8a3a45"; FOREST = "#3a6b4a"
MUST = "#c08a2e"; SLATE = "#5b6b7b"; GRAY = "#9aa3ab"; PLUM = "#6b4a6b"
OUT = r"D:\프랑스 업데이트\TNSE 스페셜이슈 논문\IS-Raft-LAC\submission\figures"

# ---------------- REAL measured data (mm_adaptive_results.txt) ----------------
rho   = np.array([0.0, 0.3, 0.6, 0.8])           # target autocorrelation floor
auc   = np.array([0.774, 0.748, 0.733, 0.819])   # adaptive (white-box PGD) AUC
anom  = np.array([0.749, 0.714, 0.704, 0.789])   # attack mean-anomaly score
acorr = np.array([0.73, 0.71, 0.74, 0.83])       # realised lag-1 autocorr
NONAD_AUC      = 0.923
NONAD_ANOM_ATK = 0.926
HEALTHY_ANOM   = 0.372
CHANCE         = 0.5
OFF_AUC        = 0.536           # constraint abandoned
WORST          = 0.733
ON_MARG, OFF_MARG = (8.0, 3.0), (7.8, 4.4)

# academic colormap (muted blue->teal->gold), colourblind-friendly
ACAD = LinearSegmentedColormap.from_list(
    "acad", ["#1d2f44", "#25405c", "#3a6b4a", "#c08a2e"])

# =============================================================================
#  COMPLEX 2D  (two information-dense panels) -- rendered both full-width
#  (side-by-side) and single-column (vertically stacked, => fig_pgd.pdf)
# =============================================================================
norm = Normalize(0.5, NONAD_AUC)
wi = int(np.argmin(auc))
x = np.arange(len(rho))


def draw_a(axa):
    """Panel (a): detection-robustness landscape."""
    xf = np.linspace(rho[0], rho[-1], 200)
    yf = np.interp(xf, rho, auc)                  # visual guide only (between
    for i in range(len(xf) - 1):                  #   measured pts; not data)
        axa.fill_between(xf[i:i+2], CHANCE, yf[i:i+2],
                         color=ACAD(norm(yf[i])), alpha=0.16, lw=0)
    axa.axhspan(0.90, 0.945, color=MUST, alpha=0.10, lw=0)
    axa.axhline(NONAD_AUC, ls=(0, (6, 2)), lw=1.2, color=MUST, zorder=2)
    axa.axhline(CHANCE, ls=(0, (1, 1.6)), lw=1.2, color=GRAY, zorder=2)
    axa.axhline(OFF_AUC, ls=(0, (4, 1.5)), lw=1.0, color=BURG, alpha=0.85,
                zorder=2)
    axa.plot(rho, auc, "-", lw=1.4, color=NAVY, zorder=3, alpha=0.55)
    axa.scatter(rho, auc, c=auc, cmap=ACAD, norm=norm, s=72,
                edgecolor="white", linewidth=1.1, zorder=5)
    for xx, yy in zip(rho, auc):
        axa.annotate(f"{yy:.3f}", (xx, yy), textcoords="offset points",
                     xytext=(0, 8.5), ha="center", fontsize=6.8,
                     color=NAVY, fontweight="bold")
    axa.scatter([rho[wi]], [auc[wi]], marker="*", s=185, color=BURG,
                edgecolor="white", linewidth=0.8, zorder=6)
    axa.annotate("worst case\n0.73", (rho[wi], auc[wi]),
                 xytext=(rho[wi] + 0.10, 0.60), fontsize=6.8, color=BURG,
                 ha="left", arrowprops=dict(arrowstyle="-", lw=0.7, color=BURG))
    axa.text(0.30, NONAD_AUC - 0.028, "non-adaptive  0.92", fontsize=6.6,
             color=MUST, ha="center", va="top", fontweight="bold")
    axa.text(0.845, CHANCE - 0.028, "chance  0.50", fontsize=6.6,
             color=GRAY, ha="right", va="top")
    axa.text(-0.04, OFF_AUC - 0.030,
             "constraint OFF 0.54\n(marginals abandon 8/3$\\to$7.8/4.4;\na mean/var test re-detects)",
             fontsize=6.0, color=BURG, ha="left", va="top")
    axa.text(0.40, 0.972, "moment-matched constraint held:  mean $=8$,  std $=3$",
             fontsize=6.2, color=SLATE, ha="center", va="center", style="italic")
    axa.set_xlim(-0.06, 0.86); axa.set_ylim(0.44, 0.985)
    axa.set_xlabel("autocorrelation floor  $\\rho_{\\min}$", fontsize=8)
    axa.set_ylabel("detection AUC", fontsize=8)
    axa.set_xticks(rho)
    axa.spines["top"].set_visible(False); axa.spines["right"].set_visible(False)
    axa.grid(axis="y", ls=":", lw=0.5, color=GRAY, alpha=0.55)
    axa.set_title("(a)  Detection robustness vs. white-box PGD",
                  fontsize=8.2, fontweight="bold", color=NAVY, pad=6)


def draw_b(axb):
    """Panel (b): adversary's realised statistics (anomaly + autocorr)."""
    axb.bar(x, anom, width=0.56, color=NAVY, alpha=0.85,
            edgecolor="white", linewidth=0.6, zorder=3)
    for xi, a in zip(x, anom):
        axb.text(xi, a + 0.012, f"{a:.2f}", ha="center", fontsize=6.4,
                 color=NAVY, fontweight="bold")
    axb.axhline(HEALTHY_ANOM, ls=(0, (5, 2)), lw=1.1, color=FOREST, zorder=2)
    axb.text(-0.42, HEALTHY_ANOM + 0.010, "healthy  0.37",
             fontsize=6.4, color=FOREST, ha="left", va="bottom")
    axb.axhline(NONAD_ANOM_ATK, ls=(0, (6, 2)), lw=1.1, color=MUST, zorder=2)
    axb.text(-0.42, NONAD_ANOM_ATK + 0.008, "non-adaptive attack  0.93",
             fontsize=6.4, color=MUST, ha="left", va="bottom")
    axb.annotate("", xy=(0.40, anom[0]), xytext=(0.40, HEALTHY_ANOM),
                 arrowprops=dict(arrowstyle="<->", lw=0.9, color=BURG))
    axb.text(0.40, (anom[0] + HEALTHY_ANOM) / 2, "residual\nseparation",
             fontsize=5.7, color=BURG, va="center", ha="center", rotation=90)
    axb.set_ylim(0.30, 1.0)
    axb.set_xticks(x); axb.set_xticklabels([f"{r:.1f}" for r in rho])
    axb.set_xlabel("autocorrelation floor  $\\rho_{\\min}$", fontsize=8)
    axb.set_ylabel("attack mean-anomaly score", fontsize=8, color=NAVY)
    axb.tick_params(axis="y", labelcolor=NAVY)
    axb.spines["top"].set_visible(False)
    axb.set_title("(b)  Adversary's realised statistics",
                  fontsize=8.2, fontweight="bold", color=NAVY, pad=6)
    axc = axb.twinx()
    axc.plot(x, acorr, "-o", lw=1.4, ms=4.5, color=BURG, mfc="white",
             mec=BURG, mew=1.0, zorder=5)
    axc.plot(x, rho, "--", lw=1.0, color=SLATE, alpha=0.8, zorder=4)
    axc.set_ylim(0.0, 1.0)
    axc.set_ylabel("lag-1 autocorrelation", fontsize=8, color=BURG)
    axc.tick_params(axis="y", labelcolor=BURG)
    axc.spines["top"].set_visible(False)
    axc.annotate("realised autocorr", (x[-1], acorr[-1]),
                 xytext=(x[-1] - 0.05, acorr[-1] + 0.085), fontsize=6.0,
                 color=BURG, ha="right")
    axc.text(0.04, 0.045, "target floor $\\rho_{\\min}$", fontsize=6.0,
             color=SLATE, ha="left", va="bottom")


# ---- full-width side-by-side (reference copy) ----
fig = plt.figure(figsize=(7.16, 3.05))
gs = fig.add_gridspec(1, 2, width_ratios=[1.18, 1.0], wspace=0.30,
                      left=0.065, right=0.965, top=0.88, bottom=0.165)
draw_a(fig.add_subplot(gs[0, 0]))
draw_b(fig.add_subplot(gs[0, 1]))
fig.savefig(OUT + r"\fig_pgd_2d.pdf")
fig.savefig(OUT + r"\fig_pgd_2d.png", dpi=200)
plt.close(fig)
print("2d (full-width) done")

# ---- single-column vertically stacked  => overwrites fig_pgd.pdf (paper) ----
fig = plt.figure(figsize=(3.5, 3.95))
gs = fig.add_gridspec(2, 1, height_ratios=[1.0, 1.0], hspace=0.52,
                      left=0.150, right=0.865, top=0.945, bottom=0.105)
draw_a(fig.add_subplot(gs[0, 0]))
draw_b(fig.add_subplot(gs[1, 0]))
fig.savefig(OUT + r"\fig_pgd.pdf")
fig.savefig(OUT + r"\fig_pgd.png", dpi=200)
plt.close(fig)
print("2d (single-column) done")

# ---- single rich panel (a) only -> fig_pgd_a.pdf (12-page-friendly option) --
fig = plt.figure(figsize=(3.5, 2.55))
fig.subplots_adjust(left=0.135, right=0.97, top=0.86, bottom=0.20)
axsingle = fig.add_subplot(111)
draw_a(axsingle)
axsingle.set_title("Detection robustness vs. white-box PGD",
                   fontsize=8.4, fontweight="bold", color=NAVY, pad=6)
fig.savefig(OUT + r"\fig_pgd_a.pdf")
fig.savefig(OUT + r"\fig_pgd_a.png", dpi=200)
plt.close(fig)
print("2d (panel-a only) done")

# =============================================================================
#  3D version  (measured operating points in AUC x autocorr x rho space)
# =============================================================================
fig = plt.figure(figsize=(6.6, 5.2))
ax = fig.add_subplot(111, projection="3d")

xr = (-0.05, 0.85)        # rho_min
yr = (0.64, 0.90)         # realised autocorr
zr = (0.48, 0.95)         # AUC

# reference planes: chance floor (0.5) and non-adaptive ceiling (0.923)
XX, YY = np.meshgrid(np.linspace(*xr, 2), np.linspace(*yr, 2))
ax.plot_surface(XX, YY, np.full_like(XX, CHANCE), color=GRAY, alpha=0.13,
                linewidth=0, shade=False)
ax.plot_surface(XX, YY, np.full_like(XX, NONAD_AUC), color=MUST, alpha=0.15,
                linewidth=0, shade=False)
ax.text(xr[1], yr[0], CHANCE - 0.008, "chance  0.50", color=GRAY,
        fontsize=6.6, ha="right")
ax.text(xr[1], yr[0], NONAD_AUC + 0.010, "non-adaptive ceiling  0.92",
        color=MUST, fontsize=6.6, fontweight="bold", ha="right")

# guide line through measured points
ax.plot(rho, acorr, auc, "-", lw=1.6, color=NAVY, alpha=0.6, zorder=2)

# drop lines to the chance plane + wall projections
for xi, yi, zi in zip(rho, acorr, auc):
    ax.plot([xi, xi], [yi, yi], [CHANCE, zi], ls=":", lw=0.9,
            color=SLATE, alpha=0.85)
# faint projections onto the back wall and the chance floor
ax.plot(rho, np.full_like(rho, yr[1]), auc, ls=(0, (2, 2)), lw=0.8,
        color=GRAY, alpha=0.6)
ax.plot(rho, acorr, np.full_like(rho, CHANCE), ls=(0, (2, 2)), lw=0.8,
        color=GRAY, alpha=0.6)

# measured points coloured by AUC
norm3 = Normalize(0.70, 0.83)
p = ax.scatter(rho, acorr, auc, c=auc, cmap=ACAD, norm=norm3, s=140,
               edgecolor="white", linewidth=1.2, depthshade=False, zorder=5)
for xi, yi, zi in zip(rho, acorr, auc):
    ax.text(xi, yi, zi + 0.016, f"{zi:.3f}", fontsize=6.8, color=NAVY,
            fontweight="bold", ha="center")

# worst-case marker + label
wi = int(np.argmin(auc))
ax.scatter([rho[wi]], [acorr[wi]], [auc[wi]], marker="*", s=320, color=BURG,
           edgecolor="white", linewidth=0.8, depthshade=False, zorder=6)
ax.text(rho[wi], acorr[wi], auc[wi] - 0.045, "worst case", fontsize=6.6,
        color=BURG, ha="center", fontweight="bold")

ax.set_xlim(*xr); ax.set_ylim(*yr); ax.set_zlim(*zr)
ax.set_xlabel("target floor  $\\rho_{\\min}$", fontsize=8.4, labelpad=6)
ax.set_ylabel("realised lag-$1$ autocorr.", fontsize=8.4, labelpad=6)
ax.set_zlabel("detection AUC", fontsize=8.4, labelpad=5)
ax.set_xticks(rho)
ax.tick_params(labelsize=7, pad=1.5)
ax.view_init(elev=22, azim=-52)
ax.set_box_aspect((1.05, 1.0, 0.80))
try:
    ax.set_facecolor("white")
    for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
        axis.pane.set_edgecolor("#dddddd")
        axis.pane.set_alpha(0.30)
except Exception:
    pass
ax.grid(True, ls=":", lw=0.4, alpha=0.4)

cbar = fig.colorbar(p, ax=ax, shrink=0.55, pad=0.06, aspect=16, location="right")
cbar.set_label("detection AUC", fontsize=7.2)
cbar.ax.tick_params(labelsize=6.5)

fig.subplots_adjust(left=0.0, right=0.92, top=0.99, bottom=0.04)
fig.savefig(OUT + r"\fig_pgd_3d.pdf")
fig.savefig(OUT + r"\fig_pgd_3d.png", dpi=200)
plt.close(fig)
print("3d done")
