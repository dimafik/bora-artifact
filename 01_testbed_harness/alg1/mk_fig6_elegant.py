"""Elegant redraw of Fig.6 (Transformer in the loop) -- NO red background.
White background; structure carried by neutral greys (faint excluded zone,
soft healthy envelope, light attack-window band) with a single burgundy
accent reserved for the attacked orderer's line and a slim blacklist ribbon.
Depth via subtle drop-shadows, not colour fills. Same real data
(predictor_daemon.log). Output: fig_detection_rich2.pdf."""
import re
import numpy as np
import matplotlib as mpl
mpl.use("Agg")
mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
    "pdf.fonttype": 42, "ps.fonttype": 42,
    "axes.linewidth": 0.8, "axes.edgecolor": "#2b2b2b",
    "axes.labelsize": 8.3, "axes.labelcolor": "#16202b",
    "xtick.labelsize": 7.3, "ytick.labelsize": 7.3,
    "legend.fontsize": 6.8, "legend.frameon": False,
})
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
from matplotlib.ticker import AutoMinorLocator

BURG="#8a3a45"; STEEL="#5f7fa6"; STEELF="#9fb4cc"; INK="#16202b"
GREY="#8a929b"; LGREY="#c9ced4"
SH = [pe.SimpleLineShadow(offset=(1.0, -1.1), alpha=0.18, rho=0.3), pe.Normal()]
PSH = [pe.withSimplePatchShadow(offset=(1.0, -1.0), alpha=0.25)]
OUT = r"D:\프랑스 업데이트\TNSE 스페셜이슈 논문\IS-Raft-LAC\submission\figures"

T0 = 1781166010.661344533
T1 = 1781166060.930663452
THRESH = 0.65
LOG = r"D:\fabric-d2\results\predictor_daemon.log"

t = []; sc = {i: [] for i in range(1, 6)}; rt = {i: [] for i in range(1, 6)}; bl = []
for line in open(LOG):
    m = re.match(r"([0-9.]+) Bt=\[([0-9,]*)\] scores=(.*)", line)
    if not m:
        continue
    ts = float(m.group(1))
    if ts < T0 - 16:
        continue
    trip = re.findall(r"o(\d):([0-9.]+)\(rtt(\d+)\)", m.group(3))
    if len(trip) < 5:
        continue
    t.append(ts - T0)
    bl.append(3 in {int(z) for z in m.group(2).split(",") if z})
    ds = {int(a): float(b) for a, b, _ in trip}
    dr = {int(a): float(c) for a, _, c in trip}
    for i in range(1, 6):
        sc[i].append(ds[i]); rt[i].append(dr[i])
t = np.array(t); bl = np.array(bl)
H = [1, 2, 4, 5]
hmin = np.min([sc[i] for i in H], axis=0); hmax = np.max([sc[i] for i in H], axis=0)


def style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.xaxis.set_minor_locator(AutoMinorLocator(2))
    ax.yaxis.set_minor_locator(AutoMinorLocator(2))
    ax.tick_params(which="both", length=3, width=0.7, color="#555")
    ax.tick_params(which="minor", length=1.6)


fig = plt.figure(figsize=(3.5, 3.35))
gs = fig.add_gridspec(2, 1, height_ratios=[2.05, 1.0], hspace=0.12,
                      left=0.155, right=0.95, top=0.945, bottom=0.13)
ax1 = fig.add_subplot(gs[0]); ax2 = fig.add_subplot(gs[1], sharex=ax1)
ax1.set_xlim(t.min(), t.max()); ax1.set_ylim(0.30, 1.0)

# faint neutral attack-window band (grey, not red)
ax1.axvspan(0, T1 - T0, color="#000000", alpha=0.038, lw=0, zorder=0)
ax2.axvspan(0, T1 - T0, color="#000000", alpha=0.038, lw=0, zorder=0)
# faint "excluded" zone below threshold (neutral)
ax1.axhspan(0.30, THRESH, color="#000000", alpha=0.030, lw=0, zorder=0)

# healthy envelope: soft steel band + thin lines
ax1.fill_between(t, hmin, hmax, color=STEELF, alpha=0.45, lw=0, zorder=1)
for i in H:
    ax1.plot(t, sc[i], "-", color=STEEL, lw=0.8, alpha=0.9, zorder=2)
# attacked orderer: single burgundy accent line + subtle shadow (no fill)
l3, = ax1.plot(t, sc[3], "-", color=BURG, lw=1.9, zorder=4); l3.set_path_effects(SH)

# threshold
ax1.axhline(THRESH, color=INK, ls=(0, (5, 3)), lw=0.9, zorder=3)
ax1.text(t.max(), THRESH + 0.012, "blacklist threshold", fontsize=6.2,
         color="#444", ha="right", va="bottom")
# attack-window bracket
ax1.annotate("", xy=(0, 0.95), xytext=(T1 - T0, 0.95),
             arrowprops=dict(arrowstyle="|-|,widthB=0.4,widthA=0.4", lw=0.8,
                             color=INK))
ax1.text((T1 - T0) / 2, 0.965, r"$+500$ ms delay on $o_3$", ha="center",
         va="bottom", fontsize=6.8, color=INK)
# detection marker + annotation
det_t = next((tt for tt, s in zip(t, sc[3]) if tt >= 0 and s < THRESH), None)
ax1.plot([det_t], [THRESH], "o", ms=5, mfc="white", mec=BURG, mew=1.3,
         zorder=6, path_effects=PSH)
ax1.annotate(f"detected\n$+{det_t:.1f}$ s", xy=(det_t, THRESH),
             xytext=(det_t + 12, 0.575), fontsize=6.6, color=BURG, ha="left",
             va="center", arrowprops=dict(arrowstyle="->", lw=0.7, color=BURG))

# slim blacklist ribbon (event track) instead of a full red background
yb0, yb1 = 0.315, 0.345
ax1.fill_between(t, yb0, yb1, where=bl, color=BURG, alpha=0.85, lw=0, zorder=5,
                 step="post")
ra = np.where(bl)[0]
ax1.text(t[ra[-1]] + 1.5, (yb0 + yb1) / 2, r"$o_3 \in \mathcal{B}_t$",
         fontsize=6.4, color=BURG, ha="left", va="center")

ax1.set_ylabel("Leader-suitability score")
style(ax1)
ax1.legend(handles=[plt.Line2D([], [], color=BURG, lw=1.9),
                    plt.Line2D([], [], color=STEEL, lw=2.6, alpha=0.55)],
           labels=[r"$o_3$ (attacked)", r"$o_{1,2,4,5}$ (healthy)"],
           loc="center right", bbox_to_anchor=(0.995, 0.40),
           handlelength=1.8, labelspacing=0.3)
plt.setp(ax1.get_xticklabels(), visible=False)

# ---- bottom: measured RTT (neutral depth, no red fill) ----
r3 = np.array(rt[3])
ax2.fill_between(t, 0, r3, color=LGREY, alpha=0.55, lw=0, zorder=1)
lr, = ax2.plot(t, r3, "-", color=BURG, lw=1.6, zorder=4); lr.set_path_effects(SH)
for i in H:
    ax2.plot(t, rt[i], "-", color=STEEL, lw=0.8, alpha=0.85, zorder=2)
ax2.annotate(r"$o_3$ RTT $\to 500$ ms", xy=(t[np.argmax(r3)], r3.max()),
             xytext=(27, 355), fontsize=6.6, color=BURG, ha="left",
             arrowprops=dict(arrowstyle="->", lw=0.7, color=BURG))
ax2.text(t.max(), 22, r"healthy $\approx 0$", fontsize=6.2, color=STEEL,
         ha="right", va="bottom")
ax2.set_ylabel("Measured RTT (ms)")
ax2.set_xlabel("Time relative to attack onset (s)")
ax2.set_ylim(-15, 560)
style(ax2)

fig.savefig(OUT + r"\fig_detection_rich2.pdf")
fig.savefig(OUT + r"\fig_detection_rich2.png", dpi=200)
plt.close(fig)
print(f"elegant detection: pts={len(t)} det={det_t:.2f}s rtt_max={r3.max():.0f}")
