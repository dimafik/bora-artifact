#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BORA predictor - Multi-Head Self-Attention over a telemetry TIME SERIES.
Publication-style, equation-free, built on the standard AI self-attention.

Adds two things over v3:
  (1) makes explicit WHY the input is a time series  -- tokens are consecutive
      Raft heartbeat ticks; a healthy orderer is temporally autocorrelated,
      a delayed/Byzantine one breaks that pattern, so the model must read the
      whole 64-tick sequence (a per-tick threshold cannot);
  (2) presents the canonical Transformer self-attention -- time tokens +
      positional encoding -> Q/K/V -> 4 heads -> tick-to-tick attention map
      -> concat -> projection.

Faithful to tnse_submission68.tex Sec. III.E (reference 17,185-param model):
  64 ticks x 5 channels -> Linear+PosEnc 64 x 32 -> Encoder x2
  [MHSA(4 heads, d_k=8) + Add&Norm + FFN(GELU) + Add&Norm]
  -> mean-pool 32 -> risk head 2 -> (risk p_t, confidence c_t).

Run:  python draw_bora_attention_v4.py
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle
import matplotlib.patheffects as pe

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10})

L, D_IN, D_MODEL, N_HEADS = 64, 5, 32, 4
D_K = D_MODEL // N_HEADS
CHAN = ["CC", "RTT", r"$\Lambda$", r"$\lambda$", r"$\tau$"]
INK, SLATE = "#1f2937", "#52617a"
INDIGO = ("#eaeafb", "#5b5bd6"); AMBER = ("#fdebc4", "#cf8616")
GREEN = ("#dcf3e3", "#1f9d57"); GREY = ("#eef1f5", "#9aa6b2")
RED = ("#fde2e2", "#d23b3b"); CYAN = ("#d9f3f7", "#118a9e"); WHITE = ("white", INK)
HEADC = [("#fbe3b0", "#cf8616"), ("#cdeeea", "#1f8e85"),
         ("#dcd9f7", "#5b5bd6"), ("#f6d6df", "#cf5f7e")]
SHADOW = pe.withSimplePatchShadow(offset=(1.3, -1.3), alpha=0.12)


def rbox(ax, x, y, w, h, col, text="", fs=10, lw=1.5, bold=False, shadow=True,
         rd=0.05, tcol=INK):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={rd}",
                 facecolor=col[0], edgecolor=col[1], linewidth=lw, zorder=3,
                 path_effects=[SHADOW] if shadow else None))
    if text:
        ax.text(x+w/2, y+h/2, text, ha="center", va="center", fontsize=fs,
                color=tcol, weight="bold" if bold else "normal", zorder=5)


def conn(ax, p0, p1, label="", lw=1.7, rad=0.0, fs=8.5, color=SLATE, style="-|>",
         loff=(0, 1.0)):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle=style, mutation_scale=14, lw=lw,
                 color=color, zorder=2, shrinkA=2, shrinkB=2,
                 connectionstyle=f"arc3,rad={rad}"))
    if label:
        ax.text((p0[0]+p1[0])/2+loff[0], (p0[1]+p1[1])/2+loff[1], label, ha="center",
                va="center", fontsize=fs, color=SLATE, zorder=6,
                bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=.9))


def grid(ax, x, y, w, h, nr, nc, data, cmap, ec="white", lw=0.4, z=4):
    cw, ch = w/nc, h/nr
    for i in range(nr):
        for j in range(nc):
            ax.add_patch(Rectangle((x+j*cw, y+(nr-1-i)*ch), cw, ch,
                         facecolor=cmap(data[i, j]), edgecolor=ec, lw=lw, zorder=z))


fig = plt.figure(figsize=(16, 11))
ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 162); ax.set_ylim(0, 108)
ax.axis("off")

# =====================================================================
#  BAND 1 - end-to-end pipeline
# =====================================================================
yT, hT = 98, 7
rbox(ax, 3, yT, 15, hT, WHITE, "Telemetry\ntime series", fs=9)
ax.text(10.5, yT-1.9, r"$64\times5$", ha="center", fontsize=8, color=SLATE)
rbox(ax, 22, yT, 14, hT, INDIGO, "Linear embed\n+ pos. enc.", fs=8.8)
conn(ax, (18, yT+hT/2), (22, yT+hT/2), r"$64\times5$")
ecx, ecw = 40, 18
ax.add_patch(FancyBboxPatch((ecx-1.4, yT-3.6), ecw+2.8, hT+7, boxstyle="round,pad=0,rounding_size=0.05",
             facecolor="#fbfaf6", edgecolor=AMBER[1], lw=1.4, linestyle=(0, (5, 3)),
             zorder=2, path_effects=[SHADOW]))
ax.text(ecx+ecw/2, yT+hT+3.6, r"Transformer encoder $\times2$", ha="center", fontsize=9,
        weight="bold", color=AMBER[1])
rbox(ax, ecx, yT+hT-3.0, ecw, 2.8, AMBER, "Multi-Head Self-Attn", fs=7.8, bold=True, lw=1.1)
rbox(ax, ecx, yT+hT-6.1, ecw, 2.8, GREEN, "Feed-Forward (GELU)", fs=7.8, lw=1.1)
mhsa_anchor = (ecx+ecw/2, yT+hT-3.0)
conn(ax, (36, yT+hT/2), (ecx-1.4, yT+hT/2), r"$64\times32$")
rbox(ax, 63, yT, 12, hT, INDIGO, "Temporal\nmean-pool", fs=8.8)
conn(ax, (ecx+ecw+1.4, yT+hT/2), (63, yT+hT/2), r"$64\times32$")
rbox(ax, 80, yT, 10, hT, RED, "Risk head", fs=8.8)
conn(ax, (75, yT+hT/2), (80, yT+hT/2), r"$32$")
rbox(ax, 95, yT+hT-3.2, 14, 3.0, RED, r"risk  $p_t$", fs=8.5, bold=True)
rbox(ax, 95, yT-0.2, 14, 3.0, CYAN, r"confidence  $c_t$", fs=8.5, bold=True)
conn(ax, (90, yT+hT/2), (95, yT+hT-1.7), rad=.2)
conn(ax, (90, yT+hT/2), (95, yT+1.3), rad=-.2, label=r"$2$")
ax.text(118, yT+hT/2, r"$\Rightarrow\ \mathcal{B}_t$ (BORA advisor)", ha="left",
        va="center", fontsize=9, weight="bold", color=INK)

# =====================================================================
#  BAND 2 - the input is a TIME SERIES + why
# =====================================================================
ax.add_patch(FancyBboxPatch((3, 58), 156, 32, boxstyle="round,pad=0,rounding_size=0.015",
             facecolor="#f7faff", edgecolor=INDIGO[1], lw=1.4, linestyle=(0, (4, 3)),
             zorder=1, path_effects=[SHADOW]))
ax.text(6, 87.5, "1.  The input is a time series of Raft heartbeat ticks",
        fontsize=12, weight="bold", color=INDIGO[1])

# timeline grid: 5 channels x 14 representative ticks
gx, gy, gw, gh = 11, 66, 66, 15
nc = 14
ts = np.zeros((D_IN, nc))
xs = np.linspace(0, 1, nc)
for r in range(D_IN):
    ts[r] = 0.30 + 0.45*np.abs(np.sin(xs*3 + r*0.7))
ts[1, 9:] = 0.95           # RTT spike late in window (attacked orderer)
grid(ax, gx, gy, gw, gh, D_IN, nc, ts, plt.cm.YlOrRd, z=4)
ax.add_patch(Rectangle((gx, gy), gw, gh, fill=False, edgecolor=INK, lw=1.4, zorder=6))
for r in range(D_IN):
    ax.text(gx-1.2, gy+gh-(r+0.5)*gh/D_IN, CHAN[r], ha="right", va="center",
            fontsize=8.5, color=INK, zorder=6)
ax.text(gx-5.5, gy+gh/2, "5 channels", rotation=90, ha="center", va="center",
        fontsize=8.2, color=SLATE)
# time axis
conn(ax, (gx, gy-2.2), (gx+gw, gy-2.2), color=SLATE, style="-|>", lw=1.4)
ax.text(gx, gy-4.4, r"$t-63$", ha="center", fontsize=8, color=SLATE)
ax.text(gx+gw, gy-4.4, r"$t$ (now)", ha="center", fontsize=8, color=SLATE)
ax.text(gx+gw/2, gy-4.6, "one token = one tick = 100 ms heartbeat    "
        r"$\bullet$    64 ticks $\approx$ 6.4 s of history",
        ha="center", fontsize=8.4, color=INK)
ax.text(gx+gw/2, gy+gh+1.3, "each column = one telemetry snapshot (a token)",
        ha="center", fontsize=8.4, color=SLATE, style="italic")

# why-time-series note
ax.add_patch(FancyBboxPatch((85, 62.5), 71, 22, boxstyle="round,pad=0.4,rounding_size=0.04",
             facecolor="white", edgecolor="#c7d0dc", lw=1.1, zorder=3))
ax.text(87, 82.6, "Why a time series (not one snapshot)?", fontsize=10.2,
        weight="bold", color=INK, zorder=4)
why = ("$\\bullet$  A healthy orderer's telemetry is temporally autocorrelated\n"
       "    (AR(1)): each tick depends on the previous ones.\n"
       "$\\bullet$  A delayed / Byzantine orderer can match a single tick's mean\n"
       "    and variance, but it breaks the cross-tick temporal pattern.\n"
       "$\\bullet$  A per-tick threshold sees only 'now' and is blind to this.\n"
       "$\\bullet$  Self-attention reads the whole 64-tick sequence at once, so\n"
       "    it captures the temporal structure that reveals the attacker.")
ax.text(87, 72.3, why, fontsize=8.5, color=INK, va="center", zorder=4, linespacing=1.45)

# arrow band2 -> band3
conn(ax, (gx+gw/2, 58), (78, 50.5), color=INDIGO[1], lw=1.8, rad=0)
ax.text(70, 54, "embed each tick + add positional encoding (tick order)",
        ha="center", fontsize=8.3, color=INDIGO[1], style="italic")

# =====================================================================
#  BAND 3 - standard self-attention over the 64 time tokens
# =====================================================================
ax.add_patch(FancyBboxPatch((3, 5), 156, 47, boxstyle="round,pad=0,rounding_size=0.012",
             facecolor="#fffdf8", edgecolor=AMBER[1], lw=1.5, linestyle=(0, (4, 3)),
             zorder=1, path_effects=[SHADOW]))
ax.text(6, 49.5, "2.  Standard multi-head self-attention over the 64 time tokens   "
        r"($d_{\mathrm{model}}=32 \rightarrow h=4$ heads $\times\, d_k=8$)",
        fontsize=12, weight="bold", color=AMBER[1])
ax.add_patch(FancyArrowPatch(mhsa_anchor, (40, 52), arrowstyle="-", lw=1.0,
             color=AMBER[1], linestyle=(0, (3, 3)), zorder=1))

# tokens
tx, ty = 8, 22
tok = np.tile(np.linspace(0.2, 0.85, 16), (8, 1))
grid(ax, tx, ty, 13, 18, 8, 16, tok, plt.cm.Blues, z=4)
ax.add_patch(Rectangle((tx, ty), 13, 18, fill=False, edgecolor=INK, lw=1.4, zorder=6))
ax.text(tx+6.5, ty+19.4, "64 time tokens", ha="center", fontsize=9, weight="bold", color=INK)
ax.text(tx+6.5, ty-1.9, r"$64\times32$", ha="center", fontsize=8, color=SLATE)
ax.text(tx-1.6, ty+9, "time", rotation=90, ha="center", va="center", fontsize=7.6, color=SLATE)

# Q K V
qx = 27
for j, nm in enumerate(["Q", "K", "V"]):
    yy = 35 - j*6.5
    rbox(ax, qx, yy, 9, 5, CYAN, nm, fs=11, bold=True, shadow=False, lw=1.3)
    ax.text(qx+4.5, yy-1.4, r"$64\times32$", ha="center", fontsize=7.2, color=SLATE)
    conn(ax, (tx+13, ty+9), (qx, yy+2.5), rad=0.05)
ax.text(qx+4.5, 41.4, "linear\n$Q,K,V$", ha="center", fontsize=8.4, color=INK)

# split into heads bar
sx, sw = 41, 20
ax.text(sx+sw/2, 41.6, "split features into 4 heads", ha="center", fontsize=8.8,
        weight="bold", color=INK)
seg = sw/N_HEADS
for k in range(N_HEADS):
    rbox(ax, sx+k*seg, 35.5, seg-0.4, 4.6, HEADC[k], f"h{k+1}", fs=8, bold=True,
         shadow=False, lw=1.2)
ax.text(sx+sw/2, 33.2, r"each head = an $8$-d subspace ($4\times8=32$)", ha="center",
        fontsize=8, color=SLATE)
conn(ax, (qx+9, 31), (sx, 37.8), rad=0)

# per-head attention (head1 expanded + ghosts)
for k in range(N_HEADS-1, 0, -1):
    off = k*1.5
    ax.add_patch(FancyBboxPatch((70+off, 11-off), 44, 27, boxstyle="round,pad=0,rounding_size=0.02",
                 facecolor=HEADC[k][0], edgecolor=HEADC[k][1], lw=1.1, zorder=2+(N_HEADS-k)))
ax.add_patch(FancyBboxPatch((70, 11), 44, 27, boxstyle="round,pad=0,rounding_size=0.02",
             facecolor="#fffaf0", edgecolor=HEADC[0][1], lw=1.6, zorder=7, path_effects=[SHADOW]))
ax.text(72, 35.2, "head 1  (each head attends over all 64 ticks)", fontsize=8.6,
        weight="bold", color=HEADC[0][1], zorder=9)
rbox(ax, 72, 25, 7.5, 4.6, HEADC[0], r"$Q_1$", fs=9.5, bold=True, shadow=False, lw=1.1)
rbox(ax, 72, 18.5, 7.5, 4.6, HEADC[0], r"$K_1$", fs=9.5, bold=True, shadow=False, lw=1.1)
ax.text(75.7, 16.8, r"$64\times8$", ha="center", fontsize=7, color=SLATE, zorder=9)
# attention map (tick x tick)
am = np.fromfunction(lambda i, j: np.exp(-((i-j)**2)/6.0), (10, 10))
am[7:, :] += 0.5; am = am/am.max()
grid(ax, 85, 17.5, 12, 12, 10, 10, am, plt.cm.YlOrRd, z=8)
ax.add_patch(Rectangle((85, 17.5), 12, 12, fill=False, edgecolor=INK, lw=1.3, zorder=9))
ax.text(91, 30.0, "attention map", ha="center", fontsize=8, weight="bold", color=INK, zorder=9)
ax.text(91, 15.7, r"tick $\times$ tick  ($64\times64$)", ha="center", fontsize=7.4, color=SLATE, zorder=9)
ax.text(98.4, 23.5, "keys = ticks", rotation=90, ha="center", va="center", fontsize=6.8,
        color=SLATE, zorder=9)
conn(ax, (79.5, 27.3), (85, 26), rad=0); conn(ax, (79.5, 20.8), (85, 20), rad=0)
rbox(ax, 101, 21, 7.5, 4.6, HEADC[0], r"$V_1$", fs=9.5, bold=True, shadow=False, lw=1.1)
conn(ax, (97, 22.5), (101, 23), label="")
ax.text(104.8, 19.2, "weighted\nsum", ha="center", fontsize=7, color=SLATE, zorder=9)
conn(ax, (108.5, 23.5), (114, 23.5), label=r"head$_1$: $64\times8$", fs=7.6, loff=(0, 1.5))

# concat + projection
rbox(ax, 122, 22, 13, 9, GREEN, "Concat\n4 heads", fs=9)
ax.text(128.5, 20.0, r"$64\times32$", ha="center", fontsize=7.6, color=SLATE)
for k in range(N_HEADS):
    conn(ax, (114+(N_HEADS-1-k)*1.5, 23.5-(N_HEADS-1-k)*1.5), (122, 29-k*1.5),
         lw=0.9, color=HEADC[k][1])
rbox(ax, 122, 9.5, 13, 7, CYAN, "Linear\nprojection", fs=9)
conn(ax, (128.5, 22), (128.5, 16.5), label=r"$64\times32$")
conn(ax, (128.5, 9.5), (128.5, 6.5))
ax.text(141, 13, "to Add & Norm\n(then FFN)", ha="center", fontsize=8.4,
        weight="bold", color=INK)

fig.text(0.5, 0.982, "BORA predictor  -  Multi-Head Self-Attention over a telemetry time series",
         ha="center", fontsize=14.5, weight="bold", color=INK)

fig.savefig("bora_attention_arch_v4.png", dpi=210, bbox_inches="tight", facecolor="white")
fig.savefig("bora_attention_arch_v4.pdf", bbox_inches="tight", facecolor="white")
print("wrote bora_attention_arch_v4.png / .pdf")
