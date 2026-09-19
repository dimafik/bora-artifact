# Draws TWO figures, and only one of them is live.
#
# LIVE, first half (to line 127): fig_detection_ac.pdf is the paper's Fig. 4,
# the detector in the loop for Section V-B.  It reads the daemon log directly
# and hardcodes nothing.
#
# CORRECTED: LOG used to be D:\fabric-d2\results\predictor_daemon.log, the
# running daemon's own file.  The filter below is a lower bound only, so that
# read ~54 s of cycles the daemon logged after the harness had already stopped
# -- the figure spanned ~137 s while Section V-B reports a single 84 s run --
# and that file is 236 MB and excluded from the artifact, so the figure could
# not be regenerated from what ships.  LOG now names the per-run copy, which
# holds exactly the 158 cycles Section V-B reports and is in the artifact.
# ships that same log at
# 02_results_raw/mldetect_20260611-171955/predictor_daemon.log.
#
# RETRACTED, second half (from line 131): fig_pgd_ac.pdf hardcodes the AUC
# series 0.774/0.748/0.733/0.819, which Section V-E retracts -- it came from a
# single restart initialised at autocorrelation 0.85, so the search never
# entered the low-correlation region it existed to explore.  Do not re-run
# that half.  The paper's white-box figure is Fig. 7, drawn by
# 10_figures/revision/mk_fig_whitebox.py from panel2_results.json.
"""Top-journal academic redraw of the ML-in-loop detection figure (now Fig. 4)
and the old white-box PGD figure, from the SAME real data as before. Sober
IEEE-Transactions
style: restrained palette (near-black + greys + one muted accent), distinguished
by line-style/marker so it survives greyscale, regular-weight labels, inward
ticks, minor ticks, no decorative colour fills, no callout chartjunk.
The white-box panel has NO worst-case marker (per request).
Outputs: fig_detection_ac.pdf, fig_pgd_ac.pdf."""
import os
import re
import numpy as np
import matplotlib as mpl
mpl.use("Agg")
mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "pdf.fonttype": 42, "ps.fonttype": 42,
    "axes.linewidth": 0.7, "axes.edgecolor": "#2b2b2b",
    "axes.labelsize": 8.5, "axes.labelcolor": "#1a1a1a",
    "xtick.labelsize": 7.5, "ytick.labelsize": 7.5,
    "xtick.color": "#1a1a1a", "ytick.color": "#1a1a1a",
    "xtick.direction": "in", "ytick.direction": "in",
    "legend.fontsize": 7.0, "legend.frameon": False,
})
import matplotlib.pyplot as plt
from matplotlib.ticker import AutoMinorLocator

INK   = "#1a1a1a"     # primary lines / text
ACC   = "#7a2e34"     # one muted accent (attacked / key series)
MID   = "#5e6b78"     # secondary series
GREY  = "#9aa3ab"     # healthy / faint
LGREY = "#c8ccd1"     # reference lines
OUT   = r"D:\프랑스 업데이트\TNSE 스페셜이슈 논문\IS-Raft-LAC\submission\figures"


def _finish(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.tick_params(which="both", length=3.2, width=0.7)
    ax.tick_params(which="minor", length=1.8)
    ax.xaxis.set_minor_locator(AutoMinorLocator(2))
    ax.yaxis.set_minor_locator(AutoMinorLocator(2))


# =====================================================================
#  Fig. 4 (LIVE) -- ML-in-the-loop detection (real predictor_daemon.log)
# =====================================================================
T0 = 1781166010.661344533
T1 = 1781166060.930663452
THRESH = 0.65
LOG = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "..", "..", "02_results_raw",
                   "mldetect_20260611-171955", "predictor_daemon.log")

t, sc = [], {i: [] for i in range(1, 6)}
for line in open(LOG):
    m = re.match(r"([0-9.]+) Bt=\[[0-9,]*\] scores=(.*)", line)
    if not m:
        continue
    ts = float(m.group(1))
    if ts < T0 - 16:
        continue
    pairs = dict(re.findall(r"o(\d):([0-9.]+)", m.group(2)))
    if len(pairs) < 5:
        continue
    t.append(ts - T0)
    for i in range(1, 6):
        sc[i].append(float(pairs[str(i)]))
t = np.array(t)

fig, ax = plt.subplots(figsize=(3.5, 2.55))
fig.subplots_adjust(left=0.145, right=0.97, top=0.90, bottom=0.165)

# neutral attack window (light grey, no colour); thin top rule + plain label
ax.axvspan(0, T1 - T0, color="#000000", alpha=0.045, lw=0, zorder=0)
ax.annotate("", xy=(0, 0.935), xytext=(T1 - T0, 0.935),
            arrowprops=dict(arrowstyle="|-|,widthB=0.35,widthA=0.35",
                            lw=0.7, color=INK))
ax.text((T1 - T0) / 2, 0.945, r"$+500$ ms delay on $o_3$", ha="center",
        va="bottom", fontsize=6.8, color=INK)

# blacklist threshold (thin dashed) + plain label
ax.axhline(THRESH, color=INK, ls=(0, (5, 3)), lw=0.8, zorder=1)
ax.text(t.max() + 2.0, THRESH + 0.012, "blacklist threshold", fontsize=6.6,
        color="#444444", ha="right", va="bottom")

# healthy orderers: thin grey (one legend proxy)
for i in [1, 2, 4, 5]:
    ax.plot(t, sc[i], "-", color=GREY, lw=0.7, alpha=0.95, zorder=2)
# attacked orderer: muted accent, heavier -> distinct in greyscale too
ax.plot(t, sc[3], "-", color=ACC, lw=1.5, zorder=4)

# detection crossing: small open marker + plain annotation (no colour callout)
det_t = next((tt for tt, s in zip(t, sc[3]) if tt >= 0 and s < THRESH), None)
if det_t is not None:
    ax.plot([det_t], [THRESH], "o", ms=4.5, mfc="white", mec=INK,
            mew=0.9, zorder=6)
    ax.annotate(f"detected ($+{det_t:.1f}$ s)", xy=(det_t, THRESH),
                xytext=(det_t + 12, 0.555), fontsize=6.8, color=INK,
                ha="left", va="center",
                arrowprops=dict(arrowstyle="-", lw=0.6, color=INK))

ax.set_xlabel("Time relative to attack onset (s)")
ax.set_ylabel("Predicted leader-suitability score")
ax.set_ylim(0.3, 0.97)
ax.set_xlim(t.min(), t.max() + 2.0)   # 2 s margin: the recovery step sits at the end
_finish(ax)

leg = ax.legend(
    handles=[plt.Line2D([], [], color=ACC, lw=1.5),
             plt.Line2D([], [], color=GREY, lw=0.9)],
    labels=[r"$o_3$ (attacked)", r"$o_{1,2,4,5}$ (healthy)"],
    loc="lower left", handlelength=1.9, borderpad=0.3, labelspacing=0.3)
fig.savefig(OUT + r"\fig_detection_ac.pdf")
fig.savefig(OUT + r"\fig_detection_ac.png", dpi=200)
plt.close(fig)
print(f"detection: points={len(t)} det={det_t:.2f}s o3_min={min(sc[3]):.3f}")

# =====================================================================
#  RETRACTED -- the old white-box PGD figure; superseded by Fig. 7, which
#  10_figures/revision/mk_fig_whitebox.py draws from panel2_results.json.
#  A header is not enough for a script that runs, so this half now exits
#  instead of redrawing a withdrawn figure.  Nothing below is reachable.
# =====================================================================
raise SystemExit("Fig. 4 written.  The white-box half is retracted; Fig. 7 is "
                 "drawn by 10_figures/revision/mk_fig_whitebox.py.")

rho = np.array([0.0, 0.3, 0.6, 0.8])
auc = np.array([0.774, 0.748, 0.733, 0.819])
NONAD, CHANCE = 0.923, 0.50

fig, ax = plt.subplots(figsize=(3.5, 2.55))
fig.subplots_adjust(left=0.145, right=0.965, top=0.95, bottom=0.165)

# reference levels: thin, neutral, plain labels (distinct dashes for greyscale)
ax.axhline(NONAD, color=INK, ls=(0, (6, 2)), lw=0.8, zorder=1)
ax.text(0.80, NONAD - 0.016, "non-adaptive (0.92)", fontsize=6.6,
        color="#444444", ha="right", va="top")
ax.axhline(CHANCE, color=INK, ls=(0, (1, 2)), lw=0.8, zorder=1)
ax.text(0.80, CHANCE + 0.012, "chance (0.50)", fontsize=6.6,
        color="#444444", ha="right", va="bottom")

# the adaptive-AUC curve: single sober series, filled markers, no fill/no star
ax.plot(rho, auc, "-", color=INK, lw=1.1, zorder=3)
ax.plot(rho, auc, "o", ms=5, mfc=ACC, mec="white", mew=0.9, zorder=4)
for x, y in zip(rho, auc):
    ax.annotate(f"{y:.3f}", (x, y), textcoords="offset points",
                xytext=(0, 7), ha="center", fontsize=6.5, color=INK)

ax.set_xlabel(r"Autocorrelation floor  $\rho_{\min}$")
ax.set_ylabel("Detection AUC")
ax.set_xlim(-0.05, 0.85)
ax.set_ylim(0.46, 0.97)
ax.set_xticks(rho)
_finish(ax)
ax.legend(handles=[plt.Line2D([], [], color=INK, lw=1.1, marker="o",
                              mfc=ACC, mec="white", ms=5)],
          labels=["white-box PGD (adaptive)"], loc="lower center",
          bbox_to_anchor=(0.5, -0.02), handlelength=1.9)
fig.savefig(OUT + r"\fig_pgd_ac.pdf")
fig.savefig(OUT + r"\fig_pgd_ac.png", dpi=200)
plt.close(fig)
print("pgd: min AUC =", auc.min(), "(no worst-case marker)")
