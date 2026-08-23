#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BORA predictor - Multi-Head Self-Attention architecture (polished, 100% faithful).

Same rich layout as bora_attention_archietecture1.png
(Input | BORA Predictor Block | Risk Head & Output  +  per-head specialization)
but every label corrected to match tnse_submission68.tex Sec. III.E exactly:

  * 5 telemetry channels  CC, RTT, Lambda (log-rep lag), lambda (ack rate),
    tau (vote-grant rate)        -- NOT 12 generic network metrics
  * window L = 64 ticks, t-63..t, one tick = 100 ms heartbeat (~6.4 s)
  * Embedding + Positional Encoding
  * Multi-Head Self-Attention, 4 heads, d_model=32, d_k=8
  * Feed-Forward (GELU) + Add & Norm (residual), Transformer encoder x2
  * 17,185 parameters (reference model)
  * output {benign, risk} logits -> temperature softmax -> risk p_t, confidence c_t
  * head 3 = heartbeat-periodic (NO 'daily load / seasonality': the 6.4 s
    window cannot carry diurnal structure)

If attn_real.npy ([4,n,n]) is present it is used for the four head maps.

Run:  python draw_bora_attention_v6_full.py
"""
import os, numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle, Wedge, Circle
import matplotlib.patheffects as pe

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9})

INK, SLATE = "#1f2937", "#5b6878"
PANEL = ("#fbfcfe", "#c2ccd9")
HEAD_BAR = "#27364b"
INDIGO = ("#e9e9fb", "#5b5bd6"); AMBER = ("#fdebc4", "#cf8616")
GREEN = ("#dcf3e3", "#1f9d57"); GREY = ("#eef1f5", "#8a97a6")
RED = ("#fde2e2", "#d23b3b"); CYAN = ("#d9f3f7", "#118a9e")
ACMAP = "viridis"
SH = pe.withSimplePatchShadow(offset=(1.2, -1.2), alpha=0.10)
CH = [("CC", "commit contribution"), ("RTT", "round-trip time"),
      (r"$\Lambda$", "log-rep lag"), (r"$\lambda$", "ack rate"),
      (r"$\tau$", "vote-grant rate")]
ROLES = [("Head 1: Local", "nearby ticks (fast AR(1) change)"),
         ("Head 2: Baseline", "distant ticks (slow trend)"),
         ("Head 3: Periodic", "heartbeat-periodic structure"),
         ("Head 4: Onset", "attack-onset tick (anomaly)")]


def rbox(ax, x, y, w, h, col, t="", fs=9, lw=1.3, bold=False, shadow=True, rd=0.05, tcol=INK):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={rd}",
                 facecolor=col[0], edgecolor=col[1], linewidth=lw, zorder=4,
                 path_effects=[SH] if shadow else None))
    if t:
        ax.text(x+w/2, y+h/2, t, ha="center", va="center", fontsize=fs, color=tcol,
                weight="bold" if bold else "normal", zorder=6)


def panel(ax, x, y, w, h, title):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.02",
                 facecolor=PANEL[0], edgecolor=PANEL[1], linewidth=1.5, zorder=2,
                 path_effects=[SH]))
    ax.add_patch(FancyBboxPatch((x, y+h-3.2), w, 3.2, boxstyle="round,pad=0,rounding_size=0.02",
                 facecolor=HEAD_BAR, edgecolor=HEAD_BAR, zorder=3))
    ax.text(x+w/2, y+h-1.6, title, ha="center", va="center", color="white",
            fontsize=10.5, weight="bold", zorder=5)


def arr(ax, p0, p1, lw=1.6, color=SLATE, rad=0.0, lab="", fs=7.5):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=13, lw=lw,
                 color=color, zorder=5, shrinkA=2, shrinkB=2,
                 connectionstyle=f"arc3,rad={rad}"))
    if lab:
        ax.text((p0[0]+p1[0])/2, (p0[1]+p1[1])/2+1.4, lab, ha="center", fontsize=fs,
                color=SLATE, zorder=7, bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=.9))


def amap(ax, x, y, w, h, A, ec, z=8):
    ax.imshow(A/(A.max()+1e-9), extent=[x, x+w, y, y+h], origin="lower",
              cmap=ACMAP, aspect="auto", zorder=z)
    ax.add_patch(Rectangle((x, y), w, h, fill=False, edgecolor=ec, lw=1.4, zorder=z+1))


def patterns(n=64):
    ii, jj = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
    onset = int(n*0.72)
    P = [np.exp(-((ii-jj)**2)/8.0),
         np.exp(-((ii-jj)**2)/600.0) + 0.12,
         0.5+0.5*np.cos((ii-jj)*2*np.pi/6.0),
         np.exp(-((jj-onset)**2)/12.0) + 0.03]
    # reorder to Local, Baseline, Periodic, Onset
    return [p/p.sum(axis=1, keepdims=True) for p in P]


real = None
if os.path.exists("attn_real.npy"):
    a = np.load("attn_real.npy")
    if a.ndim == 3 and a.shape[0] >= 4:
        real = [a[i] for i in range(4)]
maps = real if real is not None else patterns()
SRC = "real trained weights" if real is not None else "representative attention (illustrative)"

# =====================================================================
fig = plt.figure(figsize=(16, 9.3))
ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 160); ax.set_ylim(0, 93)
ax.axis("off")
fig.patch.set_facecolor("white")

# ============================ PANEL A: Input ============================
panel(ax, 2, 46, 36, 45, "Input")
# 5 channel sparklines
t = np.linspace(0, 1, 64)
for r, (sym, name) in enumerate(CH):
    yb = 84 - r*6.4
    sig = 0.5 + 0.35*np.sin(t*7 + r)
    if r == 1:                     # RTT spike late in window (attacked orderer)
        sig = sig*0.5; sig[46:] = 0.95
    ax.plot(6 + t*26, yb + sig*4.2, color="#2563eb", lw=1.1, zorder=5)
    ax.text(4.6, yb+2, sym, ha="right", va="center", fontsize=9.5, color=INK, zorder=6)
    ax.text(34, yb+2, name, ha="right", va="center", fontsize=6.6, color=SLATE, zorder=6)
# time axis
arr(ax, (6, 52.5), (32, 52.5), lw=1.3)
ax.text(6, 50.6, r"$t-63$", ha="center", fontsize=7.5, color=SLATE)
ax.text(32, 50.6, r"$t$ (now)", ha="center", fontsize=7.5, color=SLATE)
ax.text(20, 48.6, "5 channels x 64 ticks   (1 tick = 100 ms heartbeat, ~6.4 s)",
        ha="center", fontsize=7.2, color=INK)
ax.text(20, 88.0, "telemetry time series", ha="center", fontsize=8, style="italic", color=SLATE)

# ===================== PANEL B: BORA Predictor Block =====================
panel(ax, 41, 46, 86, 45, "BORA Predictor Block")
# embedding + positional encoding
rbox(ax, 44, 60, 12, 18, INDIGO, "Embedding\nLayer\n\n+\n\nPositional\nEncoding", fs=8.2)
arr(ax, (38, 68), (44, 69), lab=r"$64\times5$")
ax.text(50, 58.4, r"$\rightarrow\ 64\times32$", ha="center", fontsize=7, color=SLATE)
# MHSA box with 4 mini heads
mx, mw = 59, 38
ax.add_patch(FancyBboxPatch((mx, 55), mw, 28, boxstyle="round,pad=0,rounding_size=0.03",
             facecolor="#fffdf6", edgecolor=AMBER[1], lw=1.4, zorder=4, path_effects=[SH]))
ax.text(mx+mw/2, 81.3, "Multi-Head Self-Attention  (4 heads)", ha="center",
        fontsize=9, weight="bold", color=AMBER[1], zorder=6)
for k in range(4):
    hx = mx+1.5 + k*(mw-3)/4
    amap(ax, hx, 60.5, (mw-3)/4-1.2, 14, maps[k], AMBER[1], z=8)
    ax.text(hx+((mw-3)/4-1.2)/2, 75.7, ROLES[k][0], ha="center", fontsize=6.6,
            weight="bold", color=INK, zorder=9)
    ax.text(hx+((mw-3)/4-1.2)/2, 58.9, f"h{k+1}", ha="center", fontsize=6.4, color=SLATE, zorder=9)
ax.text(mx+mw/2, 56.0, r"$d_{\mathrm{model}}{=}32\ \rightarrow\ 4$ heads $\times\, d_k{=}8$",
        ha="center", fontsize=7, color=SLATE, zorder=9)
arr(ax, (56, 69), (mx, 69))
# FFN + Add&Norm
rbox(ax, mx+mw+1.5, 58, 9, 25, GREEN, "Feed-\nForward\n(GELU)", fs=8)
arr(ax, (mx+mw, 69), (mx+mw+1.5, 69))
rbox(ax, mx+mw+12, 58, 9, 25, GREY, "Add &\nNorm", fs=8)
arr(ax, (mx+mw+10.5, 69), (mx+mw+12, 69))
arr(ax, (mx+mw+21, 69), (124, 69))
# encoder x2 bracket + param annotation
ax.annotate("", xy=(mx, 84.5), xytext=(mx+mw+21, 84.5),
            arrowprops=dict(arrowstyle="-", lw=1.3, color=SLATE,
                            connectionstyle="bar,fraction=0.04"), zorder=6)
ax.text(mx+(mw+21)/2, 86.7, r"Transformer encoder  $\times\,2$   "
        r"(17,185 parameters)", ha="center", fontsize=8, weight="bold", color=SLATE, zorder=6)
ax.text(mx+mw/2, 53.2, "residual + LayerNorm after attention and FFN", ha="center",
        fontsize=6.5, color=SLATE, style="italic", zorder=6)

# ===================== PANEL C: Risk Head & Output =====================
panel(ax, 130, 46, 28, 45, "Risk Head & Output")
rbox(ax, 133, 72, 22, 8, RED, r"logits $\{$benign, risk$\}$"+"\n"+r"$\rightarrow$ temp. softmax", fs=7.6)
arr(ax, (127, 69), (130, 69))
# risk gauge
gx, gy, R = 144, 62, 9
for a0, a1, c in [(180, 120, "#1f9d57"), (120, 60, "#e0a93c"), (60, 0, "#d23b3b")]:
    ax.add_patch(Wedge((gx, gy), R, a1, a0, width=3.0, facecolor=c, edgecolor="white",
                       lw=0.8, zorder=6))
pv = 0.84
ang = np.radians(180*(1-pv))
ax.add_patch(FancyArrowPatch((gx, gy), (gx+R*0.86*np.cos(ang), gy+R*0.86*np.sin(ang)),
             arrowstyle="-|>", mutation_scale=10, lw=2.0, color=INK, zorder=7))
ax.add_patch(Circle((gx, gy), 0.7, facecolor=INK, zorder=8))
ax.text(gx, gy-3.0, r"risk  $p_t$", ha="center", fontsize=9, weight="bold", color=INK, zorder=7)
arr(ax, (144, 72), (144, 71.5))
# confidence bar
rbox(ax, 134, 50, 20, 5.2, CYAN, "", shadow=True)
ax.add_patch(Rectangle((135, 51), 0.78*18, 3.2, facecolor=CYAN[1], zorder=6))
ax.text(144, 56.6, r"confidence  $c_t$", ha="center", fontsize=8.5, weight="bold", color=INK, zorder=7)
ax.text(157.5, 47.6, r"$\rightarrow\ \mathcal{B}_t\ (|\mathcal{B}_t|<f)$", ha="right",
        fontsize=8, color=INK, zorder=7)

# =============== BOTTOM: per-head specialization (large maps) ===============
panel(ax, 2, 2, 156, 41, "Interpretable Attention-Head Specialization "
      "(complementary patterns over the 64-tick sequence)")
labels_qkv = True
for k in range(4):
    cx = 8 + k*38
    amap(ax, cx, 8, 26, 24, maps[k], AMBER[1], z=8)
    ax.text(cx+13, 33.0, ROLES[k][0], ha="center", fontsize=9.5, weight="bold",
            color=["#cf8616", "#1f8e85", "#5b5bd6", "#cf5f7e"][k], zorder=9)
    ax.text(cx+13, 5.6, ROLES[k][1], ha="center", fontsize=7.4, color=SLATE, zorder=9)
    if k == 0:
        ax.text(cx-1.6, 20, "query tick", rotation=90, ha="center", va="center",
                fontsize=6.6, color=SLATE, zorder=9)
        ax.text(cx+13, 6.9, "key tick", ha="center", fontsize=6.6, color=SLATE, zorder=9)

ax.text(157.5, 0.7, SRC, ha="right", fontsize=6, color="#9aa6b2", style="italic")
fig.text(0.5, 0.985, "BORA predictor - Multi-Head Self-Attention over a 5-channel telemetry time series",
         ha="center", fontsize=14, weight="bold", color=INK)

fig.savefig("bora_attention_arch_v6.png", dpi=300, bbox_inches="tight", facecolor="white")
fig.savefig("bora_attention_arch_v6.pdf", bbox_inches="tight", facecolor="white")
print(f"wrote bora_attention_arch_v6.png / .pdf   [{SRC}]")
