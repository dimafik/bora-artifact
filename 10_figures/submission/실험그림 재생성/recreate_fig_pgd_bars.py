# RETRACTED NUMBERS.  The AUC series 0.774/0.748/0.733/0.819 hardcoded below
# is the figure Section V-F now retracts: it came from a single restart
# initialised at autocorrelation 0.85.  Kept for provenance only.
# Do not re-run to produce a figure; see recreate_fig_pgd_corrected.py.
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fig 7 (white-box PGD), third pass: grouped bars instead of curves.

Data source is unchanged -- panel2_results.json, the corrected run with hard
projection back into the threat model after every step, 4 initialisations x 3
learning rates x 3 seeds = 36 combinations per floor, all feasible, worst case
reported.  The retracted 0.774/0.748/0.733/0.819 and the generator that
hardcodes them (recreate_fig_pgd.py) are not used here or anywhere.

Why bars.  As curves, four of the six detectors sit at exactly 1.000 for the
two higher floors, so they are drawn on top of one another and no combination
of colour, dash and marker can separate them -- the reader cannot tell whether
one, two or four families are represented there.  The floor takes four discrete
values, so lines were also implying a continuum that was never measured.
Grouped bars give every family its own slot at every floor: nothing is hidden,
and the saturation reads as six equal bars rather than as one line.

Our own series is annotated because its four values are the ones the text
quotes, and at the two low floors its bars are close enough to zero that the
axis alone would not report them.  Those labels are placed against the group's
own headroom, which the neighbouring bars never reach.

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

ROOT = r"D:\프랑스 업데이트\TNSE 스페셜이슈 논문"
SRC = os.path.join(ROOT, "experiments", "08_predictor", "r12_panel",
                   "panel2_results.json")
OUT = os.path.join(ROOT, "리비전", "figures", "fig_pgd_bars")

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
    "xtick.major.size": 0.0,
    "ytick.major.size": 2.5,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "pdf.fonttype": 42,
})

BURGUNDY = "#8b2e4a"
NAVY = "#2b4a68"
FOREST = "#3a6b5c"
PLUM = "#7a5680"
SLATE = "#8b9aa8"
MUSTARD = "#c09a3e"
RULE = "#8d959c"

RHOS = ["rho_0.0", "rho_0.3", "rho_0.6", "rho_0.8"]
XT = ["0", "0.3", "0.6", "0.8"]

# key -> (legend label, fill colour)
STYLE = {
    "Transformer": ("Transformer (ours)", BURGUNDY),
    "GRU":         ("GRU",                NAVY),
    "MLP":         ("MLP",                FOREST),
    "1D-CNN":      ("1D-CNN",             PLUM),
    "std(dRTT)":   ("std($\\Delta$RTT)",  SLATE),
    "logistic":    ("logistic",           MUSTARD),
}


def load():
    with open(SRC, encoding="utf-8") as fh:
        data = json.load(fh)
    rows = []
    for e in data:
        rows.append({
            "name": e["name"],
            "key": next((k for k in STYLE if e["name"].startswith(k)), None),
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
    others = sorted((r for r in rows if r["differentiable"] and r is not ours),
                    key=lambda r: r["auc"][0])
    assert len(others) == 5 and all(r["key"] for r in others), [r["name"] for r in others]
    series = [ours] + others

    fig, ax = plt.subplots(figsize=(WIDTH_IN, HEIGHT_IN), layout="constrained")

    n = len(series)
    bw = 0.115
    span = n * bw
    for si, r in enumerate(series):
        label, colour = STYLE[r["key"]]
        xs = [g - span / 2 + bw * (si + 0.5) for g in range(4)]
        ax.bar(xs, r["auc"], width=bw * 0.92, color=colour, label=label,
               edgecolor="white", linewidth=0.35,
               zorder=4 if r is ours else 3)

    # Annotate only our bars that are too short to read off the axis.  The
    # taller two are plainly visible, and labelling them would put text across
    # the neighbouring bars.  Text runs leftwards from our bar's right edge,
    # over our own bar and the empty gap before the group -- never over another
    # family's bar, since ours is the leftmost slot in each group.
    for g, v in enumerate(ours["auc"]):
        if v >= 0.10:
            continue
        ax.annotate("%.3f" % v, (g - span / 2 + bw, v), xytext=(1, 2.5),
                    textcoords="offset points", ha="right", va="bottom",
                    fontsize=5.9, color=BURGUNDY, fontweight="bold", zorder=6)

    ax.axhline(0.5, color=RULE, lw=0.8, ls=(0, (4.5, 2.8)), zorder=5)
    # the leading gap is the only column of the axes no bar occupies
    ax.annotate("chance", (-0.76, 0.5), xytext=(0, 2.0),
                textcoords="offset points", fontsize=6.0, color="#6f767c",
                ha="left", va="bottom", zorder=6)

    leg = ax.legend(ncol=3, fontsize=6.2, loc="lower center",
                    bbox_to_anchor=(0.5, 1.005), handlelength=1.1,
                    handleheight=0.85, handletextpad=0.4, columnspacing=0.8,
                    labelspacing=0.32, borderpad=0.2, borderaxespad=0.0,
                    frameon=False)
    leg.set_zorder(9)

    ax.set_xticks(range(4))
    ax.set_xticklabels(XT)
    ax.set_xlabel("autocorrelation floor  $\\rho_{\\min}$", labelpad=2.0)
    ax.set_ylabel("worst-case detection AUC", labelpad=2.0)
    ax.set_xlim(-0.80, 3.48)
    ax.set_ylim(0.0, 1.10)
    ax.set_yticks([0.0, 0.25, 0.5, 0.75, 1.0])
    ax.yaxis.grid(True, color="#e3e7ea", lw=0.55, ls=(0, (2.5, 2.5)))
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)

    fig.savefig(OUT + ".pdf", facecolor="white")
    fig.savefig(OUT + ".png", facecolor="white")

    print("wrote %s.pdf / .png  (%.2f x %.2f in)" % (OUT, WIDTH_IN, HEIGHT_IN))
    print("%-20s %s" % ("", "  ".join("rho=%s" % t for t in XT)))
    for r in series:
        print("  %-18s %s  (non-adaptive %.4f)"
              % (STYLE[r["key"]][0], "  ".join("%6.4f" % v for v in r["auc"]),
                 r["non_adaptive"]))
    ties = [XT[i] for i in range(4)
            if len({round(r["auc"][i], 4) for r in series}) < len(series)]
    print("곡선이었다면 겹쳤을 floor:", ties or "없음", "-> 막대는 슬롯이 분리됨")


if __name__ == "__main__":
    sys.exit(main())
