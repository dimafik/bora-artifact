#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BORA predictor - Multi-Head Self-Attention architecture.
Polished layout faithful to bora_attention_archietecture2.png (Input panel with
an Input-Sequence preview, BORA Predictor Block with MHSA/FFN/Norm/Output-
Prediction, Risk gauge, and a bottom head-specialization row with Q/Key/V),
with EVERY label matched to tnse_submission68.tex Sec. III.B/III.E at 100%:

  Input        : 5 Raft telemetry channels  CC, RTT, Lambda, lambda, tau
                 (NOT 12 generic network metrics) over a 64-tick window
                 t-63..t (1 tick = 100 ms heartbeat, ~6.4 s).
  Predictor    : Embedding + Positional Encoding (64x5 -> 64x32);
                 Multi-Head Self-Attention (4 heads, d_model=32, d_k=8);
                 Feed-Forward (GELU); Add & Norm; Transformer encoder x2;
                 17,185 parameters; per-orderer output prediction.
  Output       : {benign, risk} logits -> temperature softmax ->
                 risk p_t, confidence c_t -> bounded blacklist B_t (|B_t|<f).
  Head roles   : Local / Baseline / Periodic(HEARTBEAT) / Onset
                 (NO 'seasonality / daily load': 6.4 s carries no diurnal cycle).

If attn_real.npy ([4,n,n]) exists it is used for the four head maps.
Run:  python draw_bora_attention_v8.py
"""
import os, numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle, Wedge, Circle
import matplotlib.patheffects as pe

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})

INK, SLATE = "#1f2937", "#5b6878"
PANEL = ("#f7f9fc", "#c2ccd9"); HEAD_BAR = "#27364b"
INDIGO = ("#e9e9fb", "#5b5bd6"); AMBER = ("#fdebc4", "#cf8616")
GREEN = ("#d6f0df", "#1f9d57"); GREY = ("#eef1f5", "#8a97a6")
RED = ("#fde2e2", "#d23b3b"); CYAN = ("#d9f3f7", "#118a9e")
ACMAP = "viridis"
SH = pe.withSimplePatchShadow(offset=(1.2, -1.2), alpha=0.10)
CH = [("CC", "commit contribution"), ("RTT", "round-trip time"),
      (r"$\Lambda$", "log-replication lag"), (r"$\lambda$", "ack rate"),
      (r"$\tau$", "vote-grant rate")]
HCOL = ["#cf8616", "#1f8e85", "#5b5bd6", "#cf5f7e"]
ROLE_T = ["Head 1: Local", "Head 2: Baseline", "Head 3: Periodic", "Head 4: Onset"]
ROLE_D = ["nearby ticks (fast AR(1) change)", "distant ticks (slow trend)",
          "regular intervals (heartbeat)", "attack-onset tick (anomaly)"]


def rbox(ax, x, y, w, h, col, t="", fs=9, lw=1.3, bold=False, shadow=True, rd=0.05):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={rd}",
                 facecolor=col[0], edgecolor=col[1], linewidth=lw, zorder=4,
                 path_effects=[SH] if shadow else None))
    if t:
        ax.text(x+w/2, y+h/2, t, ha="center", va="center", fontsize=fs, color=INK,
                weight="bold" if bold else "normal", zorder=6)


def panel(ax, x, y, w, h, title):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.02",
                 facecolor=PANEL[0], edgecolor=PANEL[1], linewidth=1.5, zorder=2, path_effects=[SH]))
    ax.add_patch(FancyBboxPatch((x, y+h-3.2), w, 3.2, boxstyle="round,pad=0,rounding_size=0.02",
                 facecolor=HEAD_BAR, edgecolor=HEAD_BAR, zorder=3))
    ax.text(x+w/2, y+h-1.6, title, ha="center", va="center", color="white",
            fontsize=10.5, weight="bold", zorder=5)


def arr(ax, p0, p1, lw=1.6, color=SLATE, rad=0.0, lab="", fs=7.5):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=12, lw=lw, color=color,
                 zorder=5, shrinkA=2, shrinkB=2, connectionstyle=f"arc3,rad={rad}"))
    if lab:
        ax.text((p0[0]+p1[0])/2, (p0[1]+p1[1])/2+1.4, lab, ha="center", fontsize=fs, color=SLATE,
                zorder=7, bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=.9))


def amap(ax, x, y, w, h, A, ec, z=8):
    ax.imshow(A/(A.max()+1e-9), extent=[x, x+w, y, y+h], origin="lower", cmap=ACMAP,
              aspect="auto", zorder=z)
    ax.add_patch(Rectangle((x, y), w, h, fill=False, edgecolor=ec, lw=1.3, zorder=z+1))


def stacked(ax, x, y, w, h, n=3, dx=1.0, dy=1.0, fc="#e3ecf7", ec=SLATE, z=4):
    for i in range(n-1, -1, -1):
        ax.add_patch(FancyBboxPatch((x+i*dx, y-i*dy), w, h, boxstyle="round,pad=0,rounding_size=0.08",
                     facecolor=fc, edgecolor=ec, lw=1.0, zorder=z+(n-i), path_effects=[SH] if i == 0 else None))


def patterns(n=64):
    ii, jj = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
    onset = int(n*0.72)
    P = [np.exp(-((ii-jj)**2)/8.0),
         np.exp(-((ii-jj)**2)/600.0) + 0.12,
         0.5+0.5*np.cos((ii-jj)*2*np.pi/6.0),
         np.exp(-((jj-onset)**2)/12.0) + 0.03]
    return [p/p.sum(axis=1, keepdims=True) for p in P]


real = None
if os.path.exists("attn_real.npy"):
    a = np.load("attn_real.npy")
    if a.ndim == 3 and a.shape[0] >= 4:
        real = [a[i] for i in range(4)]
maps = real if real is not None else patterns()
SRC = "real trained weights" if real is not None else "representative attention (illustrative)"

# =====================================================================
fig = plt.figure(figsize=(16, 9.6)); fig.patch.set_facecolor("white")
ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 160); ax.set_ylim(0, 96); ax.axis("off")

# ----------------------- PANEL A: Input -----------------------
panel(ax, 2, 47, 34, 47, "Input")
t = np.linspace(0, 1, 64)
sigs = []
for r, (sym, name) in enumerate(CH):
    yb = 86 - r*5.0
    sig = 0.5 + 0.34*np.sin(t*7 + r)
    if r == 1:
        sig = sig*0.5; sig[46:] = 0.95
    sigs.append(sig)
    ax.plot(7 + t*20, yb + sig*3.2, color="#2563eb", lw=1.0, zorder=5)
    ax.text(6.0, yb+1.5, sym, ha="right", va="center", fontsize=9, color=INK, zorder=6)
    ax.text(33, yb+1.5, name, ha="right", va="center", fontsize=6.0, color=SLATE, zorder=6)
# Input-sequence preview (the 5x64 window as a heatmap)
win = np.array(sigs)                      # (5, 64)
ax.imshow(win, extent=[6, 22, 50, 59], origin="upper", cmap="Blues", aspect="auto", zorder=5)
ax.add_patch(Rectangle((6, 50), 16, 9, fill=False, edgecolor=INK, lw=1.2, zorder=6))
ax.text(14, 60.0, "Input Sequence", ha="center", fontsize=7, weight="bold", color=INK, zorder=6)
ax.text(14, 48.4, r"$t-63 \rightarrow t$   ($64\times5$)", ha="center", fontsize=6.6, color=SLATE, zorder=6)
ax.text(28.5, 54.5, "5 channels\nx 64 ticks\n\n1 tick =\n100 ms\nheartbeat\n(~6.4 s)",
        ha="center", va="center", fontsize=6.0, color=INK, zorder=6)

# ----------------- PANEL B: BORA Predictor Block -----------------
panel(ax, 39, 47, 92, 47, "BORA Predictor Block")
rbox(ax, 42, 71, 11, 12, INDIGO, "Embedding\nLayer", fs=7.8)
rbox(ax, 42, 57, 11, 12, INDIGO, "Positional\nEncoding", fs=7.8)
arr(ax, (36, 70), (42, 77), lab=r"$64\times5$")
ax.text(47.5, 55.4, r"$\rightarrow 64\times32$", ha="center", fontsize=6.6, color=SLATE)
mx, mw = 55, 39
ax.add_patch(FancyBboxPatch((mx, 55), mw, 30, boxstyle="round,pad=0,rounding_size=0.03",
             facecolor="#fffdf6", edgecolor=AMBER[1], lw=1.4, zorder=4, path_effects=[SH]))
ax.text(mx+mw/2, 83.2, "Multi-Head Self-Attention (4 heads)", ha="center", fontsize=8.4,
        weight="bold", color=AMBER[1], zorder=6)
for k in range(4):
    hx = mx+1.5 + k*(mw-3)/4; ww = (mw-3)/4-1.2
    ax.text(hx+ww/2, 80.0, ROLE_T[k], ha="center", fontsize=5.9, weight="bold", color=HCOL[k], zorder=9)
    amap(ax, hx, 63, ww, 14.5, maps[k], HCOL[k], z=8)
    ax.text(hx+ww/2, 61.2, f"h{k+1}", ha="center", fontsize=5.6, color=SLATE, zorder=9)
ax.text(mx+mw/2, 56.4, r"$d_{\mathrm{model}}{=}32 \rightarrow 4$ heads $\times\, d_k{=}8$",
        ha="center", fontsize=6.6, color=SLATE, zorder=9)
arr(ax, (53, 70), (mx, 70))
rbox(ax, mx+mw+1.5, 57, 8.5, 26, GREEN, "Feed-\nForward\n(GELU)", fs=7.2)
arr(ax, (mx+mw, 70), (mx+mw+1.5, 70))
rbox(ax, mx+mw+11, 57, 8.5, 26, GREY, "Add &\nNorm", fs=7.4)
arr(ax, (mx+mw+10, 70), (mx+mw+11, 70))
# Output Prediction stacked planes (per-orderer)
opx = mx+mw+21
stacked(ax, opx, 65, 8.5, 11, n=3, dx=1.0, dy=1.0)
ax.text(opx+5.2, 78.0, "Output\nPrediction", ha="center", fontsize=6.6, weight="bold", color=INK, zorder=12)
ax.text(opx+5.2, 63.2, "(per orderer)", ha="center", fontsize=5.6, color=SLATE, zorder=12)
arr(ax, (mx+mw+19.5, 70), (opx, 70.5))
# encoder x2 bracket
ax.annotate("", xy=(mx, 86.5), xytext=(opx+9, 86.5),
            arrowprops=dict(arrowstyle="-", lw=1.2, color=SLATE, connectionstyle="bar,fraction=0.05"), zorder=6)
ax.text((mx+opx+9)/2, 88.6, r"Transformer encoder $\times\,2$   (17,185 parameters)",
        ha="center", fontsize=7.6, weight="bold", color=SLATE, zorder=6)
arr(ax, (opx+9, 70), (133, 70))

# ----------------- PANEL C: Risk Head & Output -----------------
panel(ax, 134, 47, 24, 47, "Risk Head & Output")
rbox(ax, 136, 76, 20, 7.5, RED, r"$\{$benign, risk$\}$ logits"+"\n"+r"$\rightarrow$ temp. softmax", fs=6.8)
arr(ax, (131, 70), (134, 78))
gx, gy, R = 146, 66, 8.0
for a0, a1, c in [(180, 120, "#1f9d57"), (120, 60, "#e0a93c"), (60, 0, "#d23b3b")]:
    ax.add_patch(Wedge((gx, gy), R, a1, a0, width=2.6, facecolor=c, edgecolor="white", lw=0.8, zorder=6))
pv = 0.84; ang = np.radians(180*(1-pv))
ax.add_patch(FancyArrowPatch((gx, gy), (gx+R*0.8*np.cos(ang), gy+R*0.8*np.sin(ang)),
             arrowstyle="-|>", mutation_scale=8, lw=1.8, color=INK, zorder=7))
ax.add_patch(Circle((gx, gy), 0.6, facecolor=INK, zorder=8))
ax.text(gx, gy-2.4, r"risk  $p_t$", ha="center", fontsize=8.6, weight="bold", color=INK, zorder=7)
arr(ax, (146, 76), (146, 75.5))
rbox(ax, 137, 53.5, 18, 4.8, CYAN, "", shadow=True)
ax.add_patch(Rectangle((138, 54.3), 0.78*16, 3.1, facecolor=CYAN[1], zorder=6))
ax.text(146, 59.6, r"confidence  $c_t$", ha="center", fontsize=8.0, weight="bold", color=INK, zorder=7)
ax.text(146, 51.0, r"$\rightarrow\ \mathcal{B}_t\ (|\mathcal{B}_t|<f)$", ha="center", fontsize=7.4, color=INK, zorder=7)

# ----------------- BOTTOM: head specialization -----------------
panel(ax, 2, 2, 156, 42, "Insight: Interpretable Attention-Head Specialization "
      "(complementary patterns over the 64-tick sequence)")
for k in range(4):
    cx = 9 + k*38
    ax.text(cx+13, 34.3, ROLE_T[k], ha="center", fontsize=9.5, weight="bold", color=HCOL[k], zorder=9)
    amap(ax, cx, 9, 26, 23, maps[k], HCOL[k], z=8)
    ax.text(cx+13, 6.6, ROLE_D[k], ha="center", fontsize=7.0, color=SLATE, zorder=9)
    ax.text(cx-1.7, 23.0, "Query", rotation=90, ha="center", va="center", fontsize=6.6, color=INK, zorder=9)
    ax.text(cx-1.7, 14.5, "Key", rotation=90, ha="center", va="center", fontsize=6.6, color=INK, zorder=9)
    ax.text(cx+27.6, 20.5, "V", rotation=90, ha="center", va="center", fontsize=7.4, weight="bold", color=INK, zorder=9)

ax.text(157.5, 0.7, SRC, ha="right", fontsize=6, color="#9aa6b2", style="italic")
fig.text(0.5, 0.986, "BORA predictor - Multi-Head Self-Attention over a 5-channel telemetry time series",
         ha="center", fontsize=14, weight="bold", color=INK)

fig.savefig("bora_attention_arch_v8.png", dpi=300, bbox_inches="tight", facecolor="white")
fig.savefig("bora_attention_arch_v8.pdf", bbox_inches="tight", facecolor="white")
print(f"wrote bora_attention_arch_v8.png / .pdf   [{SRC}]")
