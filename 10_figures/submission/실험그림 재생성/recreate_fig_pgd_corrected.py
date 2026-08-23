#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Redraw Fig 7 (white-box PGD) from the corrected sweep.

The figure previously in the manuscript plotted 0.774/0.748/0.733/0.819 -- the
numbers Section V-F now retracts as an artefact of a single restart initialised
at autocorrelation 0.85.  Its generator (recreate_fig_pgd.py) hardcodes those
values, so it must not be re-run.  This script instead reads the corrected run,
panel2_results.json: hard projection back into the threat model after every
step, 4 initialisations x 3 learning rates x 3 seeds = 36 combinations per
floor, all feasible, worst case reported.

Layout notes, second pass.  The first version labelled each grey curve inline
and the labels landed underneath the other curves.  Curves are now identified
by a legend, and each detector gets its own muted hue and dash pattern instead
of six indistinguishable greys.  The legend sits above the frame rather than
inside it: the six curves converge on the top-right, our own value labels run
along the bottom-left, and an interior legend covered one or the other in every
position tried.  Our curve keeps the emphasis -- heavier stroke, open markers,
and its four values annotated.

The canvas is drawn at its final printed width (0.80\\columnwidth = 2.80in) and
saved without a tight bbox, so \\includegraphics scales it by exactly 1.0 and
the point sizes below are the point sizes in print.
"""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT = r"D:\프랑스 업데이트\TNSE 스페셜이슈 논문"
SRC = os.path.join(ROOT, "experiments", "08_predictor", "r12_panel",
                   "panel2_results.json")
OUT = os.path.join(ROOT, "리비전", "figures", "fig_pgd_corrected")

WIDTH_IN = 2.80
HEIGHT_IN = 1.95

plt.rcParams.update({
    "font.family": "Arial",
    "font.size": 7.0,
    "axes.labelsize": 7.0,
    "xtick.labelsize": 6.5,
    "ytick.labelsize": 6.5,
    "axes.linewidth": 0.7,
    "axes.edgecolor": "#4a4a4a",
    "xtick.major.width": 0.6,
    "ytick.major.width": 0.6,
    "xtick.major.size": 2.5,
    "ytick.major.size": 2.5,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "pdf.fonttype": 42,
})

# muted academic palette; the reference line stays neutral so it reads as a rule
BURGUNDY = "#8b2e4a"
NAVY = "#1f3b57"
FOREST = "#2f5d50"
PLUM = "#6b4a6e"
MUSTARD = "#a8842c"
SLATE = "#6b7a8a"
RULE = "#9aa3ab"

RHOS = ["rho_0.0", "rho_0.3", "rho_0.6", "rho_0.8"]
XT = ["0", "0.3", "0.6", "0.8"]

# display name, colour, dash pattern, marker
STYLE = {
    "Transformer": ("Transformer (ours)", BURGUNDY, (), "o"),
    "GRU":         ("GRU",                NAVY,     (0, (4, 1.6)), "s"),
    "MLP":         ("MLP",                FOREST,   (0, (1.6, 1.4)), "^"),
    "1D-CNN":      ("1D-CNN",             PLUM,     (0, (5, 1.6, 1.2, 1.6)), "D"),
    "std(dRTT)":   ("std($\\Delta$RTT)",  SLATE,    (0, (2.6, 1.4)), "v"),
    "logistic":    ("logistic",           MUSTARD,  (0, (3.4, 1.4, 1.2, 1.4)), "P"),
}


def load():
    with open(SRC, encoding="utf-8") as fh:
        data = json.load(fh)
    rows = []
    for e in data:
        key = next((k for k in STYLE if e["name"].startswith(k)), None)
        rows.append({
            "name": e["name"],
            "key": key,
            "differentiable": e["differentiable"],
            "non_adaptive": e["non_adaptive"],
            "auc": [e["sweep"][r]["worst_auc"] for r in RHOS],
            "detail": [e["sweep"][r]["best_combo"] for r in RHOS],
        })
    return rows


def main():
    rows = load()

    # the constraints the caption claims are held -- checked, not asserted
    for r in rows:
        for d in r["detail"]:
            assert abs(d["mean"] - 8.0) < 5e-3 and abs(d["std"] - 3.0) < 5e-3, r["name"]
            assert d["feasible_frac"] == 1.0, r["name"]

    ours = next(r for r in rows if r["key"] == "Transformer")
    # Only differentiable families belong on a white-box panel: the random
    # forest and k-NN have no gradient, so PGD never attacked them directly and
    # their high AUC would read as robustness rather than as inapplicability.
    others = [r for r in rows if r["differentiable"] and r is not ours]
    assert len(others) == 5 and all(r["key"] for r in others), [r["name"] for r in others]
    # draw the strongest survivors last so they sit on top where curves merge
    others.sort(key=lambda r: r["auc"][0])

    x = list(range(4))
    fig, ax = plt.subplots(figsize=(WIDTH_IN, HEIGHT_IN), layout="constrained")

    ax.axhline(0.5, color=RULE, lw=0.8, ls=(0, (5, 3)), zorder=2)
    ax.annotate("chance", (-0.06, 0.5), xytext=(0, 2.5),
                textcoords="offset points", fontsize=6.0, color="#7d858c",
                ha="left", va="bottom", zorder=3)

    for r in others:
        _, colour, dash, mk = STYLE[r["key"]]
        ax.plot(x, r["auc"], color=colour, lw=0.95, ls=dash, marker=mk, ms=2.3,
                mfc="white", mew=0.7, alpha=0.95, zorder=4)

    ax.plot(x, ours["auc"], color=BURGUNDY, lw=1.9, marker="o", ms=3.8,
            mfc="white", mew=1.2, zorder=6)

    # Values annotated on our curve.  The last one goes to the right of the
    # final marker rather than above it: at the right edge there is no headroom
    # and the curve arrives from below-left, so above and below are both taken.
    OFFS = [(0, 6), (0, 6), (-1, 7), (5, 0)]
    VAS = ["bottom", "bottom", "bottom", "center"]
    HAS = ["center", "center", "center", "left"]
    for xi, v, off, va, ha in zip(x, ours["auc"], OFFS, VAS, HAS):
        ax.annotate("%.3f" % v, (xi, v), xytext=off, textcoords="offset points",
                    ha=ha, va=va, fontsize=6.2, color=BURGUNDY,
                    fontweight="bold", zorder=7)

    handles = [Line2D([], [], color=BURGUNDY, lw=1.9, marker="o", ms=3.4,
                      mfc="white", mew=1.2, label=STYLE["Transformer"][0])]
    for r in others:
        lab, colour, dash, mk = STYLE[r["key"]]
        handles.append(Line2D([], [], color=colour, lw=0.95, ls=dash, marker=mk,
                              ms=2.3, mfc="white", mew=0.7, label=lab))
    # Legend outside the axes.  Six curves converge on the top-right and our own
    # value labels occupy the bottom-left, so there is no interior region a
    # legend can hold without covering something; putting it above the frame
    # keeps the plotting area clean.
    leg = ax.legend(handles=handles, ncol=3, fontsize=6.2,
                    loc="lower center", bbox_to_anchor=(0.5, 1.005),
                    handlelength=1.7, handletextpad=0.35, columnspacing=0.75,
                    labelspacing=0.3, borderpad=0.2, borderaxespad=0.0,
                    frameon=False)
    leg.set_zorder(9)

    ax.set_xticks(x)
    ax.set_xticklabels(XT)
    ax.set_xlabel("autocorrelation floor  $\\rho_{\\min}$", labelpad=1.5)
    ax.set_ylabel("worst-case detection AUC", labelpad=2.0)
    ax.set_xlim(-0.10, 3.38)
    ax.set_ylim(-0.05, 1.08)
    ax.set_yticks([0.0, 0.25, 0.5, 0.75, 1.0])
    ax.yaxis.grid(True, color="#e3e7ea", lw=0.55, ls=(0, (2.5, 2.5)))
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)

    fig.savefig(OUT + ".pdf", facecolor="white")
    fig.savefig(OUT + ".png", facecolor="white")

    print("wrote %s.pdf / .png  (%.2f x %.2f in)" % (OUT, WIDTH_IN, HEIGHT_IN))
    print("ours       :", ["%.4f" % v for v in ours["auc"]],
          " non-adaptive %.4f" % ours["non_adaptive"])
    for r in others:
        print("  %-18s %s" % (STYLE[r["key"]][0], ["%.4f" % v for v in r["auc"]]))
    # the legend must not sit on any curve
    lo = min(min(r["auc"][2:]) for r in others + [ours])
    print("legend 영역(x>1.5, y<0.30) 최저 곡선값 @rho>=0.6: %.4f" % lo)


if __name__ == "__main__":
    sys.exit(main())
