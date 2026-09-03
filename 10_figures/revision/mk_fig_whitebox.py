# White-box adaptive adversary, corrected.
#
# The submitted Fig. 7 plotted an AUC floor of 0.73 and called it "far above
# chance". That floor came from a single restart initialised at autocorrelation
# 0.85, so the search never entered the low-correlation region it existed to
# explore. Under a projected search -- every iterate pushed back inside the
# threat model, marginals held exactly at 8.00/3.00 -- the same detector reaches
# AUC 0.003. R3-S4 counted the 0.73 as a strength, so the withdrawn floor is
# drawn here rather than left to the letter.
#
# Read straight from the artifact so the figure cannot drift from the data:
#   08_predictor/r12_panel/panel2_results.json  (8 families x 144 runs = 1,152)
import json
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import rcParams
from matplotlib.lines import Line2D

rcParams["font.family"] = "Arial"
rcParams["font.size"] = 8
rcParams["axes.linewidth"] = 0.7
rcParams["pdf.fonttype"] = 42
# mathtext defaults to DejaVu, which would put the axis label's rho in a
# different face from every other glyph in the figure.
rcParams["mathtext.fontset"] = "custom"
rcParams["mathtext.rm"] = "Arial"
rcParams["mathtext.it"] = "Arial:italic"
rcParams["mathtext.bf"] = "Arial:bold"

NAVY = "#25405c"; BURG = "#8a3a45"; SLATE = "#5b6670"; MUST = "#b08428"

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "..", "..", "08_predictor", "r12_panel",
                   "panel2_results.json")
OUT = os.path.join(HERE, "fig_whitebox.pdf")

panel = json.load(open(SRC, encoding="utf-8"))
rhos = sorted(panel[0]["sweep"], key=lambda k: float(k.split("_")[1]))
x = [float(k.split("_")[1]) for k in rhos]
auc = {e["name"]: [e["sweep"][k]["worst_auc"] for k in rhos] for e in panel}
diff = [e["name"] for e in panel if e["differentiable"]]
ours = [n for n in diff if n.startswith("Transformer")][0]

lo = [min(auc[n][i] for n in diff) for i in range(len(x))]
hi = [max(auc[n][i] for n in diff) for i in range(len(x))]

fig, ax = plt.subplots(figsize=(3.45, 1.48))
ax.fill_between(x, lo, hi, color=SLATE, alpha=0.18, linewidth=0)
ax.plot(x, auc["random forest / summary stats"], color=MUST, lw=1.1,
        ls=(0, (4, 2)), marker="s", ms=3)
ax.plot(x, auc[ours], color=NAVY, lw=1.6, marker="o", ms=3.4)
ax.axhline(0.5, color="#999999", lw=0.6, ls=(0, (1, 2)))
ax.axhline(0.73, color=BURG, lw=0.8, ls=(0, (5, 2)))
ax.text(0.805, 0.735, "submitted floor 0.73, withdrawn", color=BURG,
        fontsize=6.3, ha="right", va="bottom")
ax.text(0.805, 0.505, "chance", color="#777777", fontsize=6.3,
        ha="right", va="bottom")
ax.annotate("0.003", xy=(0.0, 0.0027), xytext=(0.045, 0.115), color=NAVY,
            fontsize=6.8, arrowprops=dict(arrowstyle="-", color=NAVY, lw=0.6))

ax.set_xlim(-0.03, 0.83); ax.set_ylim(-0.04, 1.06)
ax.set_xticks(x); ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
ax.set_xlabel(r"lag-1 autocorrelation floor $\rho_{\min}$", labelpad=1.5)
ax.set_ylabel("worst-case AUC", labelpad=2)
ax.tick_params(length=2.5, pad=1.5)
for sp in ("top", "right"): ax.spines[sp].set_visible(False)

# Direct labels instead of a legend: at this size a legend box covers the
# random-forest line, and the three curves are far enough apart to name in place.
ax.text(0.055, 0.905, "random forest (no gradient)", color=MUST, fontsize=6.5,
        ha="left", va="center")
ax.text(0.415, 0.585, "six differentiable\nfamilies", color="#4a5560",
        fontsize=6.5, ha="center", va="center", linespacing=1.15)
ax.text(0.63, 0.175, "Transformer (ours)", color=NAVY, fontsize=6.8,
        ha="center", va="center")

fig.tight_layout(pad=0.25)
fig.savefig(OUT)
fig.savefig(OUT.replace(".pdf", ".png"), dpi=220)
print("saved", OUT)
print("Transformer:", [round(v, 4) for v in auc[ours]])
print("band lo   :", [round(v, 4) for v in lo])
print("band hi   :", [round(v, 4) for v in hi])
