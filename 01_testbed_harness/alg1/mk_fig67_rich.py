"""Rich, layered, 'dimensional' redraw of Fig.6 (ML-in-loop detection) and
Fig.7 (white-box PGD) from the SAME real data -- white background, but
information-dense and dynamic: gradient fills, soft drop-shadows, layered
translucent bands, twin axes, multi-panel cause->effect chains.
NO fabrication (only measured points); Fig.7 has NO worst-case marker.
Outputs: fig_detection_rich.pdf, fig_pgd_rich2.pdf."""
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
    "xtick.direction": "out", "ytick.direction": "out",
    "legend.fontsize": 6.8, "legend.frameon": False,
})
import matplotlib.pyplot as plt
import matplotlib.patheffects as pe
import matplotlib.colors as mcolors
from matplotlib.patches import Polygon
from matplotlib.ticker import AutoMinorLocator

NAVY="#243b53"; BURG="#8a3a45"; FOREST="#3a6b4a"; MUST="#c08a2e"
SLATE="#5b6b7b"; STEEL="#7d97ad"; GREY="#9aa3ab"; INK="#16202b"
SH = [pe.SimpleLineShadow(offset=(1.1, -1.1), alpha=0.22, rho=0.4), pe.Normal()]
PSH = [pe.withSimplePatchShadow(offset=(1.0, -1.0), alpha=0.28)]
OUT = r"D:\프랑스 업데이트\TNSE 스페셜이슈 논문\IS-Raft-LAC\submission\figures"


def grad_under(ax, x, y, ybase, color, amax=0.42, zorder=1, flip=False):
    """Vertical gradient fill between ybase and the curve y (depth cue)."""
    rgb = mcolors.to_rgb(color)
    g = np.empty((256, 1, 4)); g[:, :, :3] = rgb
    a = np.linspace(0, amax, 256)
    g[:, :, 3] = (a[::-1] if flip else a)[:, None]
    x = np.asarray(x, float); y = np.asarray(y, float)
    lo = min(ybase, float(np.min(y))); hi = max(ybase, float(np.max(y)))
    im = ax.imshow(g, aspect="auto", origin="lower",
                   extent=[x.min(), x.max(), lo, hi], zorder=zorder)
    verts = np.vstack([[x[0], ybase], np.column_stack([x, y]), [x[-1], ybase]])
    im.set_clip_path(Polygon(verts, closed=True, transform=ax.transData))
    return im


def grad_band(ax, y0, y1, color, amax=0.30, zorder=0):
    """Horizontal soft gradient band (e.g. a ceiling region) for depth."""
    rgb = mcolors.to_rgb(color)
    g = np.empty((256, 1, 4)); g[:, :, :3] = rgb
    g[:, :, 3] = np.linspace(amax, 0, 256)[:, None]
    x0, x1 = ax.get_xlim()
    ax.imshow(g, aspect="auto", origin="lower", extent=[x0, x1, y0, y1],
              zorder=zorder)


def style(ax):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.xaxis.set_minor_locator(AutoMinorLocator(2))
    ax.yaxis.set_minor_locator(AutoMinorLocator(2))
    ax.tick_params(which="both", length=3, width=0.7, color="#555")
    ax.tick_params(which="minor", length=1.6)


# =====================================================================
#  Fig.6 -- detection: RTT cause -> score -> blacklist action (3 layers)
# =====================================================================
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
    bset = set(int(z) for z in m.group(2).split(",") if z)
    bl.append(3 in bset)
    d_s = {int(a): float(b) for a, b, _ in trip}
    d_r = {int(a): float(c) for a, _, c in trip}
    for i in range(1, 6):
        sc[i].append(d_s[i]); rt[i].append(d_r[i])
t = np.array(t); bl = np.array(bl)
H = [1, 2, 4, 5]
hmin = np.min([sc[i] for i in H], axis=0); hmax = np.max([sc[i] for i in H], axis=0)

fig = plt.figure(figsize=(3.5, 4.05))
gs = fig.add_gridspec(2, 1, height_ratios=[2.15, 1.0], hspace=0.12,
                      left=0.155, right=0.95, top=0.93, bottom=0.115)
ax1 = fig.add_subplot(gs[0]); ax2 = fig.add_subplot(gs[1], sharex=ax1)

# --- blacklist-active spans (advisor action), behind everything ---
def runs(mask):
    out = []; s = None
    for k, v in enumerate(mask):
        if v and s is None: s = k
        if (not v) and s is not None: out.append((s, k - 1)); s = None
    if s is not None: out.append((s, len(mask) - 1))
    return out
for a, b in runs(bl):
    ax1.axvspan(t[a], t[b], color=BURG, alpha=0.07, lw=0, zorder=0)
    ax2.axvspan(t[a], t[b], color=BURG, alpha=0.07, lw=0, zorder=0)
ra, rb = runs(bl)[0]
ax1.text((t[ra] + t[rb]) / 2, 0.335, r"$o_3 \in \mathcal{B}_t$  (blacklisted)",
         ha="center", va="bottom", fontsize=6.4, color=BURG, style="italic")

# --- top: leader-suitability score ---
ax1.fill_between(t, hmin, hmax, color=STEEL, alpha=0.30, lw=0, zorder=1)
for i in H:
    ax1.plot(t, sc[i], "-", color=STEEL, lw=0.7, alpha=0.85, zorder=2)
grad_under(ax1, t, np.array(sc[3]), 0.3, BURG, amax=0.30, zorder=1)
l3, = ax1.plot(t, sc[3], "-", color=BURG, lw=1.8, zorder=4)
l3.set_path_effects(SH)
ax1.axhline(THRESH, color=INK, ls=(0, (5, 3)), lw=0.9, zorder=3)
ax1.text(t.max(), THRESH + 0.012, "blacklist threshold", fontsize=6.2,
         color="#444", ha="right", va="bottom")
# attack bracket
ax1.annotate("", xy=(0, 0.95), xytext=(T1 - T0, 0.95),
             arrowprops=dict(arrowstyle="|-|,widthB=0.4,widthA=0.4", lw=0.8,
                             color=INK))
ax1.text((T1 - T0) / 2, 0.965, r"$+500$ ms delay on $o_3$", ha="center",
         va="bottom", fontsize=6.8, color=INK)
det_t = next((tt for tt, s in zip(t, sc[3]) if tt >= 0 and s < THRESH), None)
ax1.plot([det_t], [THRESH], "o", ms=5, mfc="white", mec=BURG, mew=1.3,
         zorder=6, path_effects=PSH)
ax1.annotate(f"detected\n$+{det_t:.1f}$ s", xy=(det_t, THRESH),
             xytext=(det_t + 13, 0.585), fontsize=6.6, color=BURG, ha="left",
             va="center", arrowprops=dict(arrowstyle="->", lw=0.7, color=BURG))
ax1.set_ylabel("Leader-suitability score")
ax1.set_ylim(0.30, 1.0); ax1.set_xlim(t.min(), t.max())
style(ax1)
ax1.legend(handles=[plt.Line2D([], [], color=BURG, lw=1.8),
                    plt.Line2D([], [], color=STEEL, lw=2.4, alpha=0.6)],
           labels=[r"$o_3$ (attacked)", r"$o_{1,2,4,5}$ (healthy envelope)"],
           loc="center right", bbox_to_anchor=(0.995, 0.385),
           handlelength=1.8, labelspacing=0.3)
plt.setp(ax1.get_xticklabels(), visible=False)

# --- bottom: measured RTT (the physical cause) ---
r3 = np.array(rt[3])
grad_under(ax2, t, r3, 0.0, BURG, amax=0.40, zorder=1)
lr, = ax2.plot(t, r3, "-", color=BURG, lw=1.6, zorder=4); lr.set_path_effects(SH)
for i in H:
    ax2.plot(t, rt[i], "-", color=STEEL, lw=0.7, alpha=0.8, zorder=2)
ax2.annotate(r"$o_3$ RTT $\to 500$ ms", xy=(t[np.argmax(r3)], r3.max()),
             xytext=(28, 360), fontsize=6.6, color=BURG, ha="left",
             arrowprops=dict(arrowstyle="->", lw=0.7, color=BURG))
ax2.text(t.max(), 18, r"healthy $\approx 0$", fontsize=6.2, color=SLATE,
         ha="right", va="bottom")
ax2.set_ylabel("Measured RTT (ms)")
ax2.set_xlabel("Time relative to attack onset (s)")
ax2.set_ylim(-15, 560)
style(ax2)

fig.savefig(OUT + r"\fig_detection_rich.pdf")
fig.savefig(OUT + r"\fig_detection_rich.png", dpi=200)
plt.close(fig)
print(f"detection_rich: pts={len(t)} det={det_t:.2f}s o3rtt_max={r3.max():.0f}")

# =====================================================================
#  Fig.7 -- white-box PGD: AUC robustness + adversary stats (NO worst-case)
# =====================================================================
rho = np.array([0.0, 0.3, 0.6, 0.8])
auc = np.array([0.774, 0.748, 0.733, 0.819])
anom = np.array([0.749, 0.714, 0.704, 0.789])
acorr = np.array([0.73, 0.71, 0.74, 0.83])
NONAD, CHANCE, HEALTHY, NONAD_AN = 0.923, 0.50, 0.372, 0.926
ACAD = mcolors.LinearSegmentedColormap.from_list(
    "acad", ["#1d2f44", "#243b53", "#3a6b4a", "#c08a2e"])
norm = mcolors.Normalize(0.5, NONAD)

fig = plt.figure(figsize=(3.5, 3.4))
gs = fig.add_gridspec(2, 1, height_ratios=[1.22, 1.0], hspace=0.46,
                      left=0.15, right=0.86, top=0.95, bottom=0.125)
axa = fig.add_subplot(gs[0]); axb = fig.add_subplot(gs[1])

# ---- (a) AUC robustness landscape ----
xf = np.linspace(rho[0], rho[-1], 200); yf = np.interp(xf, rho, auc)
for i in range(len(xf) - 1):  # detection-margin gradient (chance -> AUC)
    axa.fill_between(xf[i:i+2], CHANCE, yf[i:i+2],
                     color=ACAD(norm(yf[i])), alpha=0.18, lw=0, zorder=1)
axa.set_xlim(-0.05, 0.85); axa.set_ylim(0.46, 0.97)
grad_band(axa, 0.90, 0.945, MUST, amax=0.32, zorder=0)
axa.axhline(NONAD, color=MUST, ls=(0, (6, 2)), lw=1.0, zorder=2)
axa.text(0.82, NONAD - 0.018, "non-adaptive (0.92)", fontsize=6.4,
         color="#7a5a16", ha="right", va="top", fontweight="bold")
axa.axhline(CHANCE, color="#555", ls=(0, (1, 2)), lw=0.9, zorder=2)
axa.text(0.82, CHANCE + 0.012, "chance (0.50)", fontsize=6.4, color="#555",
         ha="right", va="bottom")
la, = axa.plot(rho, auc, "-", color=NAVY, lw=1.5, zorder=3, alpha=0.9)
la.set_path_effects(SH)
axa.scatter(rho, auc, c=auc, cmap=ACAD, norm=norm, s=80, edgecolor="white",
            linewidth=1.2, zorder=5)
for x, y in zip(rho, auc):
    axa.annotate(f"{y:.3f}", (x, y), textcoords="offset points",
                 xytext=(0, 8), ha="center", fontsize=6.4, color=NAVY,
                 fontweight="bold")
axa.set_xticks(rho)
axa.set_xlabel(r"Autocorrelation floor  $\rho_{\min}$")
axa.set_ylabel("Detection AUC")
style(axa)
axa.set_title("(a)  Detection robustness vs. white-box PGD",
              fontsize=8.0, color=NAVY, fontweight="bold", pad=5)

# ---- (b) adversary's realised statistics ----
xb = np.arange(len(rho))
bars = axb.bar(xb, anom, width=0.58, color=NAVY, alpha=0.85, edgecolor="white",
               linewidth=0.6, zorder=3)
for b in bars:
    b.set_path_effects(PSH)
for xi, a in zip(xb, anom):
    axb.text(xi, a + 0.014, f"{a:.2f}", ha="center", fontsize=6.2, color=NAVY,
             fontweight="bold")
axb.axhline(HEALTHY, ls=(0, (5, 2)), lw=1.0, color=FOREST, zorder=2)
axb.text(-0.45, HEALTHY + 0.01, "healthy 0.37", fontsize=6.2, color=FOREST,
         ha="left", va="bottom")
axb.axhline(NONAD_AN, ls=(0, (6, 2)), lw=1.0, color=MUST, zorder=2)
axb.text(-0.45, NONAD_AN + 0.008, "non-adaptive attack 0.93", fontsize=6.2,
         color="#7a5a16", ha="left", va="bottom")
axb.annotate("", xy=(0.42, anom[0]), xytext=(0.42, HEALTHY),
             arrowprops=dict(arrowstyle="<->", lw=0.9, color=BURG))
axb.text(0.42, (anom[0] + HEALTHY) / 2, "residual\nseparation", fontsize=5.6,
         color=BURG, va="center", ha="center", rotation=90)
axb.set_ylim(0.30, 1.0)
axb.set_xticks(xb); axb.set_xticklabels([f"{r:.1f}" for r in rho])
axb.set_xlabel(r"Autocorrelation floor  $\rho_{\min}$")
axb.set_ylabel("Attack anomaly", color=NAVY)
axb.tick_params(axis="y", labelcolor=NAVY)
style(axb)
axc = axb.twinx()
lc, = axc.plot(xb, acorr, "-o", lw=1.4, ms=4.5, color=BURG, mfc="white",
               mec=BURG, mew=1.0, zorder=5); lc.set_path_effects(SH)
axc.plot(xb, rho, "--", lw=1.0, color=SLATE, alpha=0.85, zorder=4)
axc.set_ylim(0.0, 1.0)
axc.set_ylabel("lag-1 autocorr.", color=BURG)
axc.tick_params(axis="y", labelcolor=BURG)
axc.spines["top"].set_visible(False)
axc.annotate("realised autocorr", (xb[-1], acorr[-1]),
             xytext=(xb[-1] - 0.05, acorr[-1] + 0.08), fontsize=5.9, color=BURG,
             ha="right")
axc.text(0.04, 0.05, r"target floor $\rho_{\min}$", fontsize=5.9, color=SLATE,
         ha="left", va="bottom")
axb.set_title("(b)  Adversary's realised statistics",
              fontsize=8.0, color=NAVY, fontweight="bold", pad=5)

fig.savefig(OUT + r"\fig_pgd_rich2.pdf")
fig.savefig(OUT + r"\fig_pgd_rich2.png", dpi=200)
plt.close(fig)
print("pgd_rich2: 2-panel, no worst-case marker")
