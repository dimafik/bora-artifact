#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generate IEEE-quality Fig.4 / Fig.6 / Fig.7 for tnse_submission87.
Numbers are taken verbatim from the manuscript captions/body.

  Fig.4  fig_exclusion_forest  (fig:exclusion)  leadership-acquisition forest
  Fig.6  fig_detection_rich2   (fig:detect)     Transformer-in-the-loop chain
  Fig.7  fig_pgd_rich2         (fig:pgd)         white-box PGD adaptive adversary

Captions carry the titles, so the figures themselves omit titles (IEEE style).
Run:  python make_figs_4_6_7.py
"""
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 8.5,
    "axes.linewidth": 0.8, "axes.edgecolor": "#444444",
    "axes.labelsize": 9, "xtick.labelsize": 8, "ytick.labelsize": 8,
    "legend.fontsize": 7.4, "legend.frameon": False,
    "figure.dpi": 300, "savefig.dpi": 300,
})
C_BASE, C_BORA = "#c0392b", "#1f7a8c"
C_O3, C_OK, C_OKf = "#c0392b", "#5b6878", "#aab4c2"
GRID = dict(color="#cfd6df", lw=0.6, ls=(0, (3, 3)), alpha=0.9)


def despine(ax, keep=("left", "bottom")):
    for s in ("top", "right", "left", "bottom"):
        ax.spines[s].set_visible(s in keep)


def wilson(k, n, z=1.96):
    p = k/n; d = 1 + z*z/n
    c = (p + z*z/(2*n))/d
    h = (z/d)*np.sqrt(p*(1-p)/n + z*z/(4*n*n))
    return max(0.0, c-h), min(1.0, c+h), p


def save(fig, name):
    fig.savefig(name + ".pdf", bbox_inches="tight", facecolor="white")
    fig.savefig(name + ".png", bbox_inches="tight", facecolor="white")
    print("wrote", name + ".pdf / .png")
    plt.close(fig)


# ===================== Fig. 4 : leadership-acquisition forest =====================
def fig_exclusion():
    cfgs = [
        ("$N{=}5$ single-host", (7, 36), (0, 36)),
        ("$N{=}7$",             (3, 24), (0, 24)),
        ("$N{=}9$",             (8, 23), (0, 23)),
        ("5-host AWS",          (5, 16), (0, 16)),
    ]
    fig, ax = plt.subplots(figsize=(3.5, 2.65))
    ys = np.arange(len(cfgs))[::-1]
    for y, (name, (kb, nb), (kr, nr)) in zip(ys, cfgs):
        lo, hi, p = wilson(kb, nb)
        ax.plot([lo*100, hi*100], [y+0.17]*2, color=C_BASE, lw=1.5, solid_capstyle="round", zorder=3)
        for xx in (lo*100, hi*100):
            ax.plot([xx, xx], [y+0.17-0.07, y+0.17+0.07], color=C_BASE, lw=1.2, zorder=3)
        ax.scatter([p*100], [y+0.17], s=34, color=C_BASE, zorder=4, edgecolor="white", lw=0.6)
        ax.text(p*100, y+0.17+0.13, f"{p*100:.1f}%", va="bottom", ha="center", fontsize=6.6, color=C_BASE)
        lo2, hi2, p2 = wilson(kr, nr)
        ax.plot([lo2*100, hi2*100], [y-0.17]*2, color=C_BORA, lw=1.5, solid_capstyle="round", zorder=3)
        ax.plot([hi2*100, hi2*100], [y-0.17-0.07, y-0.17+0.07], color=C_BORA, lw=1.2, zorder=3)
        ax.scatter([p2*100], [y-0.17], s=34, marker="D", color=C_BORA, zorder=4, edgecolor="white", lw=0.6)
        ax.text(hi2*100+0.8, y-0.17, f"0% [0, {hi2*100:.1f}]", va="center", ha="left", fontsize=6.6, color=C_BORA)
    ax.set_yticks(ys); ax.set_yticklabels([c[0] for c in cfgs])
    ax.set_xlabel("targeted-orderer leadership-acquisition rate (%)")
    ax.set_xlim(-1.5, 44); ax.set_ylim(-0.7, len(cfgs)-0.3)
    ax.xaxis.grid(True, **GRID); ax.set_axisbelow(True); despine(ax)
    h1 = ax.scatter([], [], s=34, color=C_BASE, edgecolor="white", lw=0.6, label="baseline Raft")
    h2 = ax.scatter([], [], s=34, marker="D", color=C_BORA, edgecolor="white", lw=0.6, label="BORA")
    ax.legend(handles=[h1, h2], loc="center left", bbox_to_anchor=(1.005, 0.5), handletextpad=0.4)
    save(fig, "fig_exclusion_forest")


# ===================== Fig. 6 : Transformer-in-the-loop detection =====================
def fig_detection():
    rng = np.random.default_rng(7)
    T, dt = 30.0, 0.1; t = np.arange(0, T, dt)
    onset, end, thr = 8.0, 20.0, 0.65
    healthy_traces = [0.85 + 0.012*np.sin(t*1.3+s) + rng.normal(0, 0.007, t.size) for s in range(4)]
    score3 = np.full(t.size, 0.85)
    score3 = np.where(t >= onset, 0.85 - 0.43*np.clip((t-onset)/5.0, 0, 1), score3)
    base_at_end = 0.85 - 0.43*np.clip((end-onset)/5.0, 0, 1)
    score3 = np.where(t >= end, base_at_end + (0.85-base_at_end)*np.clip((t-end-2.0)/6.0, 0, 1), score3)
    score3 += rng.normal(0, 0.006, t.size)
    cross = onset + 3.1

    fig, (axS, axR) = plt.subplots(2, 1, figsize=(3.5, 4.0), sharex=True,
                                   gridspec_kw=dict(height_ratios=[2.05, 1.0], hspace=0.12))
    for ax in (axS, axR):
        ax.axvspan(onset, end, color="#fde2e2", alpha=0.55, lw=0, zorder=0)
    for tr in healthy_traces:
        axS.plot(t, tr, color=C_OKf, lw=1.0, zorder=2)
    axS.plot(t, score3, color=C_O3, lw=1.7, zorder=4)
    axS.axhline(thr, color="#333", lw=1.0, ls=(0, (4, 3)), zorder=3)
    axS.text(0.3, thr+0.012, "blacklist threshold 0.65", fontsize=6.6, color="#333", va="bottom")
    axS.plot([cross], [thr], marker="v", color="#b8860b", ms=6, zorder=6)
    axS.annotate("crosses 3.1 s\nafter onset", xy=(cross, thr), xytext=(cross+1.4, 0.715),
                 fontsize=6.6, color="#7a5b00", arrowprops=dict(arrowstyle="->", lw=0.8, color="#7a5b00"))
    axS.text(0.3, 0.892, "4 healthy orderers $\\approx 0.85$ (no false positive)", fontsize=6.6, color=C_OK)
    axS.text(16.0, 0.55, "$+500$ ms attack on $o_3$", fontsize=6.8, color=C_BASE, va="center", ha="center")
    axS.set_ylabel("leader-suitability\nScore"); axS.set_ylim(0.34, 0.95)
    despine(axS); axS.yaxis.grid(True, **GRID); axS.set_axisbelow(True)
    inB = score3 < thr
    axS.fill_between(t, 0.345, 0.368, where=inB, color="#c0392b", alpha=0.9, lw=0, zorder=5)
    axS.text(18.0, 0.357, "$\\mathcal{B}_t=\\{3\\}$", fontsize=6.0, color="white", va="center", ha="center", zorder=6)
    rtt3 = np.where((t >= onset) & (t < end), 500, 2.0) + rng.normal(0, 1.2, t.size)
    rtt3 = np.clip(rtt3, 0, None)
    for s in range(4):
        axR.plot(t, np.clip(2.0+rng.normal(0, 0.6, t.size), 0, None), color=C_OKf, lw=0.9, zorder=2)
    axR.plot(t, rtt3, color=C_O3, lw=1.5, zorder=4)
    axR.set_ylabel("RTT (ms)"); axR.set_xlabel("time (s)"); axR.set_ylim(-30, 560)
    despine(axR); axR.yaxis.grid(True, **GRID); axR.set_axisbelow(True)
    axR.text(onset+0.25, 508, "$o_3 \\approx 500$ ms", fontsize=6.6, color=C_BASE, va="top")
    axR.text(0.3, 70, "healthy $\\approx 0$", fontsize=6.6, color=C_OK)
    save(fig, "fig_detection_rich2")


# ===================== Fig. 7 : white-box PGD adaptive adversary =====================
def fig_pgd():
    rho = np.array([0.0, 0.3, 0.6, 0.8])
    auc = np.array([0.73, 0.78, 0.83, 0.88])
    nonadaptive, chance = 0.92, 0.50
    anom_attack = np.array([0.79, 0.76, 0.73, 0.71]); anom_healthy = 0.37

    fig, (axA, axB) = plt.subplots(1, 2, figsize=(3.5, 2.5),
                                   gridspec_kw=dict(width_ratios=[1.05, 1.0], wspace=0.46))
    axA.axhline(nonadaptive, color=C_BORA, lw=1.1, ls=(0, (5, 2)), zorder=2)
    axA.text(0.0, nonadaptive+0.006, "non-adaptive 0.92", fontsize=6.3, color=C_BORA, va="bottom")
    axA.axhline(chance, color="#888", lw=1.0, ls=(0, (1, 2)), zorder=2)
    axA.text(0.83, chance+0.006, "chance 0.50", fontsize=6.3, color="#666", va="bottom", ha="right")
    axA.plot(rho, auc, "-o", color=C_BASE, lw=1.5, ms=5, mfc="white", mew=1.3, zorder=4)
    axA.set_xlabel("autocorrelation floor $\\rho_{\\min}$"); axA.set_ylabel("detection AUC")
    axA.set_xticks(rho); axA.set_ylim(0.45, 0.97); axA.set_xlim(-0.05, 0.85)
    despine(axA); axA.yaxis.grid(True, **GRID); axA.set_axisbelow(True)
    axA.set_title("(a)", loc="left", fontsize=8.5, fontweight="bold")

    x = np.arange(len(rho))
    axB.bar(x, anom_attack, width=0.62, color=C_BASE, alpha=0.85, label="attack $o_3$", zorder=3)
    axB.axhline(anom_healthy, color=C_OK, lw=1.3, ls=(0, (4, 2)), zorder=4)
    axB.text(len(rho)-0.55, anom_healthy-0.02, "healthy 0.37", fontsize=6.3, color=C_OK, va="top", ha="right")
    axB.fill_between([-0.5, len(rho)-0.5], anom_healthy, anom_attack.min(), color="#2e7d32", alpha=0.13, lw=0, zorder=1)
    axB.text(1.5, (anom_healthy+anom_attack.min())/2, "separation", fontsize=8.0, color="#1b5e20",
             fontweight="bold", va="center", ha="center", zorder=6,
             path_effects=[pe.withStroke(linewidth=2.4, foreground="white")])
    axB.set_xticks(x); axB.set_xticklabels([f"{r:g}" for r in rho])
    axB.set_xlabel("$\\rho_{\\min}$"); axB.set_ylabel("mean anomaly score")
    axB.set_ylim(0, 0.95); axB.set_xlim(-0.6, len(rho)-0.4)
    despine(axB); axB.yaxis.grid(True, **GRID); axB.set_axisbelow(True)
    axB.set_title("(b)", loc="left", fontsize=8.5, fontweight="bold")
    save(fig, "fig_pgd_rich2")


if __name__ == "__main__":
    fig_exclusion(); fig_detection(); fig_pgd(); print("done.")
