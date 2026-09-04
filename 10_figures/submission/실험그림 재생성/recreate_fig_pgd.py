# RETRACTED NUMBERS.  The AUC series 0.774/0.748/0.733/0.819 hardcoded below
# is the figure Section V-E now retracts: it came from a single restart
# initialised at autocorrelation 0.85.  Kept for provenance only.
# Do not re-run. The figure in the paper is Fig. 7, drawn by
# 10_figures/revision/mk_fig_whitebox.py from panel2_results.json.
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Recreate fig_pgd (white-box PGD adaptive adversary) with three edits:
  (a) remove the red sentence starting with 'marginals ...';
      remove the 'worst case 0.73' annotation and its star marker
      (the rho=0.6 point is shown as a normal marker like the others);
  (b) make the green 'healthy 0.37' label clearly readable.
Numbers reproduced verbatim from the existing fig_pgd.png.
Run:  python recreate_fig_pgd.py   (writes fig_pgd.png / .pdf in this folder)
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9.5,
    "axes.linewidth": 0.9, "axes.edgecolor": "#555",
    "xtick.labelsize": 9, "ytick.labelsize": 9,
    "figure.dpi": 300, "savefig.dpi": 300,
})
NAVY, GRAY = "#1f3b57", "#7b8794"
GREEN, SLATE = "#2e7d32", "#46617d"
ORANGE, MAROON, REDC = "#d98a00", "#8b2e4a", "#a83246"
HALO = [pe.withStroke(linewidth=2.6, foreground="white")]

rho = np.array([0.0, 0.3, 0.6, 0.8])
auc = np.array([0.774, 0.748, 0.733, 0.819])
NONADAPT_AUC, CONSTR_OFF, CHANCE = 0.92, 0.54, 0.50
anom = np.array([0.75, 0.71, 0.70, 0.79])
NONADAPT_ATK, HEALTHY = 0.93, 0.37
autocorr = np.array([0.81, 0.79, 0.82, 0.88])
x = np.arange(4)                      # categorical positions
xt = ["0", "0.3", "0.6", "0.8"]


def despine(ax, keep=("left", "bottom")):
    for s in ("top", "right", "left", "bottom"):
        ax.spines[s].set_visible(s in keep)


fig, (a1, a2) = plt.subplots(2, 1, figsize=(6.6, 7.4),
                             gridspec_kw=dict(hspace=0.42))

# =========================== (a) ===========================
a1.axhspan(NONADAPT_AUC-0.006, NONADAPT_AUC+0.006, color=ORANGE, alpha=0.16, zorder=1)
a1.axhline(NONADAPT_AUC, color=ORANGE, lw=1.6, ls=(0, (6, 3)), zorder=2)
a1.text(0.0, NONADAPT_AUC+0.012, "non-adaptive  0.92", color=ORANGE, fontweight="bold",
        fontsize=10, va="bottom")
a1.fill_between(x, auc, CONSTR_OFF, color="#b5bcc4", alpha=0.30, zorder=1)
a1.plot(x, auc, color=SLATE, lw=2.2, zorder=3)
a1.scatter(x, auc, s=95, color=GREEN, edgecolor="white", lw=1.4, zorder=4)
for xi, v in zip(x, auc):
    a1.text(xi, v+0.014, f"{v:.3f}", ha="center", va="bottom", fontsize=9.5,
            fontweight="bold", color=NAVY)
a1.axhline(CONSTR_OFF, color=MAROON, lw=1.4, ls=(0, (5, 3)), zorder=2)
a1.text(0.0, CONSTR_OFF+0.008, "constraint OFF 0.54", color=MAROON, fontsize=9, va="bottom")
a1.axhline(CHANCE, color=GRAY, lw=1.3, ls=(0, (1, 2)), zorder=2)
a1.text(3.0, CHANCE+0.008, "chance  0.50", color=GRAY, fontsize=9, va="bottom", ha="right")
a1.set_xticks(x); a1.set_xticklabels(xt)
a1.set_xlabel(r"autocorrelation floor  $\rho_{\min}$")
a1.set_ylabel("detection AUC")
a1.set_ylim(0.46, 0.95); a1.set_xlim(-0.25, 3.25)
a1.yaxis.grid(True, color="#dfe4ea", lw=0.7, ls=(0, (3, 3))); a1.set_axisbelow(True)
despine(a1)
a1.set_title("(a) Detection robustness vs. white-box PGD", fontweight="bold",
             color=NAVY, fontsize=11.5, pad=20)
a1.text(0.5, 1.035, r"moment-matched constraint held:  mean = 8,  std = 3",
        transform=a1.transAxes, ha="center", fontstyle="italic", color=GRAY, fontsize=9)

# =========================== (b) ===========================
a2.bar(x, anom, width=0.6, color=SLATE, alpha=0.92, zorder=3, label="attack mean-anomaly")
# value labels placed INSIDE the bar top (white) so they never collide with the
# red realised-autocorr line/markers that float just above the bars
for xi, v in zip(x, anom):
    a2.text(xi, v-0.028, f"{v:.2f}", ha="center", va="top", fontsize=9,
            fontweight="bold", color="white", zorder=6)
a2.axhline(NONADAPT_ATK, color=ORANGE, lw=1.6, ls=(0, (6, 3)), zorder=2)
a2.text(0.0, NONADAPT_ATK+0.012, "non-adaptive attack  0.93", color=ORANGE, fontweight="bold",
        fontsize=9.5, va="bottom")
a2.axhline(HEALTHY, color=GREEN, lw=1.8, ls=(0, (6, 3)), zorder=4)
a2.text(2.5, HEALTHY+0.03, "healthy 0.37", color="#14521a", fontweight="bold",
        fontsize=10.5, ha="center", va="bottom", zorder=8, path_effects=HALO)
# residual separation marker (between healthy and the lowest attack bar)
a2.annotate("", xy=(0.5, anom.min()), xytext=(0.5, HEALTHY),
            arrowprops=dict(arrowstyle="<->", color=MAROON, lw=1.6), zorder=6)
a2.text(0.62, (HEALTHY+anom.min())/2, "residual\nseparation", color=MAROON, fontsize=8.2,
        va="center", ha="left", zorder=7, path_effects=HALO)
a2.set_xticks(x); a2.set_xticklabels(xt)
a2.set_xlabel(r"autocorrelation floor  $\rho_{\min}$")
a2.set_ylabel("attack mean-anomaly score", color=SLATE)
a2.tick_params(axis="y", colors=SLATE)
a2.set_ylim(0.0, 1.0); a2.set_xlim(-0.6, 3.6)
a2.yaxis.grid(True, color="#dfe4ea", lw=0.7, ls=(0, (3, 3))); a2.set_axisbelow(True)
despine(a2, keep=("left", "bottom"))
a2.set_title("(b) Adversary's realised statistics", fontweight="bold", color=NAVY, fontsize=11.5, pad=10)

a2r = a2.twinx()
a2r.plot(x, autocorr, color=REDC, lw=1.9, marker="o", ms=7, mfc="white", mew=1.6, zorder=5)
DGRAY = "#3f4750"
a2r.plot(x, rho, color=DGRAY, lw=1.7, ls=(0, (5, 3)), zorder=4)
a2r.text(3.0, autocorr[-1]+0.02, "realised autocorr", color=REDC, fontsize=9, ha="right", va="bottom")
a2r.text(2.0, rho[2]-0.05, r"target floor $\rho_{\min}$", color=DGRAY, fontsize=8.6,
         fontweight="bold", ha="center", va="top", path_effects=HALO)
a2r.set_ylabel("lag-1 autocorrelation", color=REDC)
a2r.tick_params(axis="y", colors=REDC)
a2r.set_ylim(0.0, 1.0)
for s in ("top",):
    a2r.spines[s].set_visible(False)
a2r.spines["right"].set_color(REDC)

fig.savefig("fig_pgd.png", bbox_inches="tight", facecolor="white")
fig.savefig("fig_pgd.pdf", bbox_inches="tight", facecolor="white")
print("wrote fig_pgd.png / fig_pgd.pdf")
