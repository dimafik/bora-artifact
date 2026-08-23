#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BORA predictor - Multi-Head Self-Attention architecture (publication figure).

Redrawn in a clean, top-tier-paper style: no inline equations, a single
left-to-right dataflow, tensor-shape annotations on the connectors, and a
visual (stacked-plane) depiction of the multi-head self-attention block.

Faithful to tnse_submission68.tex, Sec. III.E (reference 17,185-param model):
    window 64 x 5  ->  Linear+PosEnc 64 x 32  ->  Encoder x2
    (Multi-Head Self-Attention[4 heads] + Add&Norm + FFN/GELU + Add&Norm)
    ->  temporal mean-pool 32  ->  risk head 2  ->  (risk p_t, confidence c_t)

Run:  python draw_bora_attention_v2.py
Out:  bora_attention_arch_v2.png / .pdf
"""

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle
import matplotlib.patheffects as pe

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 10.5,
    "axes.linewidth": 0,
})

# ---- hyper-parameters from the paper body ----
L, D_IN, D_MODEL, N_HEADS = 64, 5, 32, 4
D_K = D_MODEL // N_HEADS          # 8
CHAN = ["CC", "RTT", r"$\Lambda$", r"$\lambda$", r"$\tau$"]

# ---- restrained academic palette ----
INK   = "#1f2937"          # near-black text / borders
SLATE = "#475569"          # connectors
BLUE  = ("#eef3fb", "#3b6db3")
INDIGO= ("#eaeafb", "#5b5bd6")
AMBER = ("#fdebc4", "#d28a16")   # attention
GREEN = ("#dcf3e3", "#1f9d57")   # FFN
GREY  = ("#eef1f5", "#9aa6b2")   # add&norm
RED   = ("#fde2e2", "#d23b3b")   # risk
CYAN  = ("#d9f3f7", "#118a9e")   # confidence / projections
SHADOW = pe.withSimplePatchShadow(offset=(1.4, -1.4), alpha=0.12)


def rbox(ax, x, y, w, h, fc, ec, text="", fs=10.5, lw=1.5, bold=False,
         shadow=True, rounding=0.04, tcol=INK):
    p = FancyBboxPatch((x, y), w, h,
                       boxstyle=f"round,pad=0.0,rounding_size={rounding}",
                       facecolor=fc, edgecolor=ec, linewidth=lw, zorder=3,
                       path_effects=[SHADOW] if shadow else None)
    ax.add_patch(p)
    if text:
        ax.text(x + w/2, y + h/2, text, ha="center", va="center",
                fontsize=fs, color=tcol, zorder=4,
                weight="bold" if bold else "normal")
    return p


def slab(ax, x, y, w, h, fc, ec, n=4, dx=0.9, dy=0.9, label="", fs=9, lw=1.3):
    """Stacked planes (back-to-front) to depict multiple heads."""
    for i in range(n-1, -1, -1):
        sh = [SHADOW] if i == 0 else None
        ax.add_patch(FancyBboxPatch((x + i*dx, y - i*dy), w, h,
                     boxstyle="round,pad=0,rounding_size=0.03",
                     facecolor=fc, edgecolor=ec, linewidth=lw, zorder=3+i,
                     path_effects=sh))
    if label:
        ax.text(x + w/2, y + h/2, label, ha="center", va="center",
                fontsize=fs, zorder=20, color=INK)


def conn(ax, p0, p1, label="", lw=1.8, rad=0.0, fs=8.5, loff=(0, 0.9),
         color=SLATE, style="-|>"):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle=style, mutation_scale=15,
                 lw=lw, color=color, zorder=2,
                 connectionstyle=f"arc3,rad={rad}",
                 shrinkA=2, shrinkB=2))
    if label:
        mx, my = (p0[0]+p1[0])/2 + loff[0], (p0[1]+p1[1])/2 + loff[1]
        ax.text(mx, my, label, ha="center", va="center", fontsize=fs,
                color=SLATE, zorder=6,
                bbox=dict(boxstyle="round,pad=0.15", fc="white",
                          ec="none", alpha=0.9))


fig = plt.figure(figsize=(13.5, 7.6))
ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 135); ax.set_ylim(0, 76)
ax.axis("off")

# =====================================================================
#  MAIN DATAFLOW  (left -> right, vertically centred at y0)
# =====================================================================
y0, bh = 47, 15

# 1) input telemetry window as a mini channel x time heatmap
ix, iw = 4, 17
rbox(ax, ix, y0, iw, bh, "white", INK, lw=1.5)
nr, nc = D_IN, 12
cw, ch = (iw-4)/nc, (bh-5)/nr
rng = np.linspace(0, 1, nc)
for r in range(nr):
    base = 0.35 + 0.45*np.sin(rng*3 + r)        # deterministic telemetry-like pattern
    if r == 1:                                   # RTT spike on the attacked window
        base[7:] = 0.95
    for c in range(nc):
        ax.add_patch(Rectangle((ix+2.0+c*cw, y0+1.0+r*ch), cw*0.92, ch*0.86,
                     facecolor=plt.cm.YlOrRd(base[c]*0.8+0.1),
                     edgecolor="white", lw=0.4, zorder=4))
    ax.text(ix+1.6, y0+1.0+r*ch+ch/2, CHAN[r], ha="right", va="center",
            fontsize=8.5, color=INK, zorder=5)
ax.text(ix+iw/2, y0+bh+2.3, "Per-orderer telemetry", ha="center",
        fontsize=10.5, weight="bold", color=INK)
ax.text(ix+iw/2, y0-2.4, r"window  $64 \times 5$", ha="center", fontsize=9.5,
        color=SLATE)

# 2) embedding + positional encoding
ex = ix + iw + 13
ew = 16
rbox(ax, ex, y0, ew, bh, INDIGO[0], INDIGO[1],
     "Linear\nembedding\n+ positional\nencoding", fs=10, bold=False)
conn(ax, (ix+iw, y0+bh/2), (ex, y0+bh/2), r"$64\times5$")

# 3) Transformer encoder x2  (container with 4 stacked sub-bars)
cx = ex + ew + 14
cw2, cbh = 24, 30
ax.add_patch(FancyBboxPatch((cx-2, y0-(cbh-bh)/2-2), cw2+4, cbh+4,
             boxstyle="round,pad=0,rounding_size=0.03",
             facecolor="#fbfaf6", edgecolor=AMBER[1], linewidth=1.6,
             linestyle=(0, (5, 3)), zorder=2, path_effects=[SHADOW]))
ax.text(cx+cw2/2, y0-(cbh-bh)/2-2+cbh+2.0, r"Transformer encoder  $\times\,2$",
        ha="center", va="bottom", fontsize=10.5, weight="bold", color=AMBER[1])
sub = [("Multi-Head Self-Attention", AMBER, True),
       ("Add & Norm", GREY, False),
       ("Feed-Forward  (GELU)", GREEN, False),
       ("Add & Norm", GREY, False)]
sh = 5.4; gap = 1.5
sy = y0 - (cbh-bh)/2 + 0.5
ys = []
for i, (t, col, bold) in enumerate(sub):
    yy = sy + i*(sh+gap)
    rbox(ax, cx, yy, cw2, sh, col[0], col[1], t, fs=9.6, bold=bold, lw=1.4)
    ys.append(yy)
mhsa_top = (cx+cw2/2, ys[0]+sh)     # callout anchor (top of MHSA bar)
mhsa_box = (cx, ys[0], cw2, sh)
conn(ax, (ex+ew, y0+bh/2), (cx-2, y0+bh/2), r"$64\times32$")

# 4) temporal mean pool
px = cx + cw2 + 14
pw = 13
rbox(ax, px, y0, pw, bh, INDIGO[0], INDIGO[1], "Temporal\nmean-pool", fs=10)
conn(ax, (cx+cw2+2, y0+bh/2), (px, y0+bh/2), r"$64\times32$")

# 5) risk head
hx = px + pw + 12
hw = 12
rbox(ax, hx, y0, hw, bh, RED[0], RED[1], "Risk\nhead\n(Linear)", fs=10)
conn(ax, (px+pw, y0+bh/2), (hx, y0+bh/2), r"$32$")

# 6) outputs -> advisor
ox = hx + hw + 11
rbox(ax, ox, y0+bh-6.2, 16, 6.0, RED[0], RED[1], "risk score  $p_t$", fs=10, bold=True)
rbox(ax, ox, y0-0.2, 16, 6.0, CYAN[0], CYAN[1], "confidence  $c_t$", fs=10, bold=True)
conn(ax, (hx+hw, y0+bh/2), (ox, y0+bh-3.2), rad=0.18, label="")
conn(ax, (hx+hw, y0+bh/2), (ox, y0+2.8), rad=-0.18, label=r"$2$")
ax.add_patch(FancyBboxPatch((ox+0.5, y0+bh+1.5), 15, 5.5,
             boxstyle="round,pad=0,rounding_size=0.4",
             facecolor="#1f2937", edgecolor="#1f2937", zorder=3,
             path_effects=[SHADOW]))
ax.text(ox+8, y0+bh+1.5+2.75, "BORA advisor", ha="center", va="center",
        color="white", fontsize=9.5, weight="bold", zorder=4)
conn(ax, (ox+8, y0+bh-0.2), (ox+8, y0+bh+1.5), rad=0, color=SLATE)

# =====================================================================
#  MULTI-HEAD SELF-ATTENTION DETAIL  (bottom inset, dashed callout)
# =====================================================================
dy0 = 6
# callout frame
ax.add_patch(FancyBboxPatch((cx-21, dy0-2), 70, 26,
             boxstyle="round,pad=0,rounding_size=0.02",
             facecolor="#fffdf8", edgecolor=AMBER[1], linewidth=1.4,
             linestyle=(0, (4, 3)), zorder=1, path_effects=[SHADOW]))
ax.text(cx-21+1.5, dy0+24-1.2, "Multi-Head Self-Attention   "
        r"($d_{\mathrm{model}}=32$,  $h=4$ heads,  $d_k=8$)",
        ha="left", va="top", fontsize=10.5, weight="bold", color=AMBER[1])
# dashed callout lines from MHSA bar to inset
for sx in (cx-19, cx+cw2+18):
    ax.add_patch(FancyArrowPatch((mhsa_top[0], mhsa_top[1]), (sx, dy0+22),
                 arrowstyle="-", lw=1.0, color=AMBER[1],
                 linestyle=(0, (3, 3)), zorder=1, shrinkA=4, shrinkB=2))

iy = dy0 + 8.5; ih = 7
# input tokens
gx = cx-17
rbox(ax, gx, iy, 12, ih, INDIGO[0], INDIGO[1], "input\ntokens", fs=9.5)
ax.text(gx+6, iy-2.3, r"$64\times32$", ha="center", fontsize=8.5, color=SLATE)
# Q / K / V projections
qx = gx + 16
for j, (nm) in enumerate(["Q", "K", "V"]):
    rbox(ax, qx, iy+ (1-j)*0.0, 6.5, ih, CYAN[0], CYAN[1], nm, fs=10.5, bold=True)
    # we stack them visually side by side
    qx += 7.5
qcx = gx + 16 + 11.0
ax.text(gx+16+11.0, iy-2.3, r"linear  $Q,K,V$", ha="center", fontsize=8.5, color=SLATE)
conn(ax, (gx+12, iy+ih/2), (gx+16, iy+ih/2), color=SLATE)

# heads as stacked planes, each = scaled dot-product attention
hx2 = qcx + 11
slab(ax, hx2, iy+1.2, 17, ih-1.0, AMBER[0], AMBER[1], n=N_HEADS,
     dx=1.5, dy=1.5, label="Scaled\nDot-Product\nAttention", fs=8.6)
ax.text(hx2+8.5+ (N_HEADS-1)*1.5/2, iy-2.3, r"$4$ heads,  each $64\times8$",
        ha="center", fontsize=8.5, color=SLATE)
conn(ax, (gx+16+22, iy+ih/2), (hx2, iy+ih/2), color=SLATE, label="split")

# concat
ccx = hx2 + 17 + 8
rbox(ax, ccx, iy, 11, ih, GREEN[0], GREEN[1], "Concat", fs=10)
conn(ax, (hx2+17+ (N_HEADS-1)*1.5, iy+ih/2), (ccx, iy+ih/2), color=SLATE)
# output projection
pcx = ccx + 14
rbox(ax, pcx, iy, 12, ih, CYAN[0], CYAN[1], "Linear\nprojection", fs=9.5)
conn(ax, (ccx+11, iy+ih/2), (pcx, iy+ih/2), color=SLATE, label=r"$64\times32$")
conn(ax, (pcx+12, iy+ih/2), (pcx+16, iy+ih/2), color=SLATE)
ax.text(pcx+16.5, iy+ih/2, "out", ha="left", va="center", fontsize=9.5,
        color=INK, weight="bold")

fig.text(0.5, 0.975, "BORA predictor  -  Multi-Head Self-Attention architecture",
         ha="center", fontsize=13.5, weight="bold", color=INK)

fig.savefig("bora_attention_arch_v2.png", dpi=220, bbox_inches="tight",
            facecolor="white")
fig.savefig("bora_attention_arch_v2.pdf", bbox_inches="tight", facecolor="white")
print("wrote bora_attention_arch_v2.png / .pdf")
