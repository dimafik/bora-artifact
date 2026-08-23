#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BORA predictor - Multi-Head Self-Attention  (IEEE single-column, compact).

Designed to drop into the paper body at column width (3.5 in).  The hero is
an explicit explanation of WHAT THE 4 HEADS ARE: four complementary attention
patterns over the 64-tick telemetry sequence.  No equations; tensor shapes only.
The "why a time series" rationale lives in the LaTeX caption, not the figure.

If  attn_real.npy  (shape [4, n, n]) is present -- produced by
extract_attention.py in a torch environment -- the four head maps are rendered
from the REAL trained weights; otherwise four labelled representative patterns
are drawn (clearly an illustration of head specialisation).

Faithful to tnse_submission68.tex Sec. III.E (17,185-param reference model):
  64 ticks x 5 ch -> Linear+PosEnc 64x32 -> Encoder x2
  [MHSA(4 heads, d_k=8) + Add&Norm + FFN(GELU) + Add&Norm] -> pool -> risk head.

Run:  python draw_bora_attention_v5.py
"""
import os, numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle
import matplotlib.patheffects as pe

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 6.2})

INK, SLATE = "#1f2937", "#5b6878"
INDIGO = ("#e9e9fb", "#5b5bd6"); AMBER = ("#fdebc4", "#cf8616")
GREEN = ("#dcf3e3", "#1f9d57"); RED = ("#fde2e2", "#d23b3b")
CYAN = ("#d9f3f7", "#118a9e"); WHITE = ("white", INK)
HEADC = [("#fbe3b0", "#cf8616"), ("#cdeeea", "#1f8e85"),
         ("#dcd9f7", "#5b5bd6"), ("#f6d6df", "#cf5f7e")]
SH = pe.withSimplePatchShadow(offset=(0.8, -0.8), alpha=0.10)
CMAP = plt.cm.YlOrRd

# four head roles (the explicit "what are the 4 heads" answer)
ROLES = [
    ("Head 1  -  Local",      "adjacent ticks (fast AR(1) change)"),
    ("Head 2  -  Long-range", "distant ticks (slow trend / baseline)"),
    ("Head 3  -  Onset",      "the attack-onset tick (change point)"),
    ("Head 4  -  Periodic",   "heartbeat-periodic structure"),
]


def rbox(ax, x, y, w, h, col, t="", fs=6.2, lw=1.0, bold=False, shadow=True, rd=0.06):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={rd}",
                 facecolor=col[0], edgecolor=col[1], linewidth=lw, zorder=3,
                 path_effects=[SH] if shadow else None))
    if t:
        ax.text(x+w/2, y+h/2, t, ha="center", va="center", fontsize=fs, color=INK,
                weight="bold" if bold else "normal", zorder=5)


def arr(ax, p0, p1, lw=1.0, color=SLATE, rad=0.0, lab="", fs=5.4):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=8, lw=lw,
                 color=color, zorder=2, shrinkA=1.5, shrinkB=1.5,
                 connectionstyle=f"arc3,rad={rad}"))
    if lab:
        ax.text((p0[0]+p1[0])/2, (p0[1]+p1[1])/2+1.0, lab, ha="center", fontsize=fs,
                color=SLATE, zorder=6, bbox=dict(boxstyle="round,pad=0.1", fc="white",
                ec="none", alpha=.9))


def heat(ax, x, y, w, h, A, ec, z=8):
    n = A.shape[0]; cw, ch = w/n, h/n
    A = A/ (A.max()+1e-9)
    for i in range(n):
        for j in range(n):
            ax.add_patch(Rectangle((x+j*cw, y+(n-1-i)*ch), cw, ch,
                         facecolor=CMAP(A[i, j]), edgecolor="none", zorder=z))
    ax.add_patch(Rectangle((x, y), w, h, fill=False, edgecolor=ec, lw=1.3, zorder=z+1))


def head_patterns(n=16):
    """Four canonical, row-normalised attention patterns (illustration)."""
    ii, jj = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
    onset = int(n*0.7)
    P = [
        np.exp(-((ii-jj)**2)/3.0),                                   # local
        np.exp(-((ii-jj)**2)/120.0) + 0.15,                          # long-range
        np.exp(-((jj-onset)**2)/4.0) + 0.03,                         # onset (vertical band)
        0.5+0.5*np.cos((ii-jj)*2*np.pi/4.0),                         # periodic stripes
    ]
    return [p/p.sum(axis=1, keepdims=True) for p in P]


# ---- load real attention if available ----
real = None
if os.path.exists("attn_real.npy"):
    a = np.load("attn_real.npy")
    if a.ndim == 3 and a.shape[0] >= 4:
        real = [a[i] for i in range(4)]
maps = real if real is not None else head_patterns()
SRC = "real trained weights (best_mm.pt)" if real is not None else "illustrative patterns"

# =====================================================================
fig = plt.figure(figsize=(3.5, 4.5))
ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 70); ax.set_ylim(0, 90)
ax.axis("off")

# ---- (a) compact end-to-end pipeline ----
y = 84.5; h = 4.6
xs = [2.0, 13.0, 24.5, 41.0, 51.5, 60.5]
defs = [(WHITE, "tele.\n64x5"), (INDIGO, "embed\n+PE"), (AMBER, "Enc\nx2"),
        (INDIGO, "pool"), (RED, "risk"), (CYAN, r"$p_t,c_t$")]
ws  = [9.5, 9.5, 14.5, 8.5, 7.0, 8.0]
for (x, w), (col, t) in zip(zip(xs, ws), defs):
    rbox(ax, x, y, w, h, col, t, fs=5.4, bold=(col is AMBER))
    if x > 2.0:
        arr(ax, (x-1.5, y+h/2), (x, y+h/2))
ax.text(0.5, y+h+1.3, "(a)", fontsize=7, weight="bold", color=INK)
# callout from Enc
arr(ax, (31.7, y), (24, 73), lw=0.8, color=AMBER[1], rad=0.0)

# ---- (b) tokens -> Q,K,V -> split into 4 heads ----
ax.text(0.5, 74.5, "(b)", fontsize=7, weight="bold", color=INK)
ax.text(35, 75.0, "self-attention over 64 time tokens  (1 token = one 100 ms tick)",
        ha="center", fontsize=6.0, weight="bold", color=INK)
rbox(ax, 3, 65, 12, 7, INDIGO, "64 tokens\n64x32", fs=5.4)
rbox(ax, 19, 68.5, 8, 4.0, CYAN, "Q", fs=6.4, bold=True, shadow=False)
rbox(ax, 19, 64.0, 8, 4.0, CYAN, "K", fs=6.4, bold=True, shadow=False)
rbox(ax, 19, 59.5, 8, 4.0, CYAN, "V", fs=6.4, bold=True, shadow=False)
for yy in (70.5, 66.0, 61.5):
    arr(ax, (15, 68.5), (19, yy), lw=0.7)
ax.text(23, 57.6, "linear Q,K,V", ha="center", fontsize=5.2, color=SLATE)
# split bar
sx, sw = 33, 30
ax.text(sx+sw/2, 73.3, r"split $d_{\mathrm{model}}{=}32$  into  4 heads $\times\,d_k{=}8$",
        ha="center", fontsize=5.8, color=INK)
for k in range(4):
    rbox(ax, sx+k*sw/4, 65.5, sw/4-0.5, 5.0, HEADC[k], f"h{k+1}", fs=5.6, bold=True,
         shadow=False, lw=1.0)
ax.text(sx+sw/2, 63.5, "(same split for Q, K, V)", ha="center", fontsize=5.0,
        color=SLATE, style="italic")
arr(ax, (27, 66), (sx, 68), lw=0.9)

# ---- (c) THE 4 HEADS: four complementary attention maps ----
ax.text(0.5, 55.5, "(c)", fontsize=7, weight="bold", color=INK)
ax.text(35, 55.8, "the 4 heads = four complementary attention patterns over time",
        ha="center", fontsize=6.2, weight="bold", color=INK)
# 2x2 grid
cells = [(6, 30), (37, 30), (6, 7.5), (37, 7.5)]   # (x,y) lower-left of each map
mw, mh = 20, 17
for k, (cx, cy) in enumerate(cells):
    heat(ax, cx, cy, mw, mh, maps[k], HEADC[k][1])
    ax.text(cx+mw/2, cy+mh+2.2, ROLES[k][0], ha="center", fontsize=5.8,
            weight="bold", color=HEADC[k][1])
    ax.text(cx+mw/2, cy+mh+0.6, ROLES[k][1], ha="center", fontsize=5.0, color=SLATE)
    # tiny axis hint on first map only
    if k == 0:
        ax.text(cx-1.4, cy+mh/2, "query tick", rotation=90, ha="center", va="center",
                fontsize=4.6, color=SLATE)
        ax.text(cx+mw/2, cy-1.4, "key tick", ha="center", fontsize=4.6, color=SLATE)
    # arrow from split head k to its map
    hkx = sx + k*sw/4 + (sw/4-0.5)/2
    arr(ax, (hkx, 65.5), (cx+mw/2, cy+mh), lw=0.7, color=HEADC[k][1], rad=0.0)

# ---- (d) concat + projection ----
ax.text(0.5, 4.2, "(d)", fontsize=7, weight="bold", color=INK)
ax.text(35, 4.2, "concat 4 heads (64x32)  ->  linear projection  ->  Add & Norm  ->  FFN",
        ha="center", fontsize=5.8, color=INK)
for k, (cx, cy) in enumerate(cells):
    arr(ax, (cx+mw/2, cy), (35, 5.6), lw=0.6, color=HEADC[k][1], rad=0.0)

ax.text(69.5, 0.6, SRC, ha="right", fontsize=4.4, color="#9aa6b2", style="italic")

fig.savefig("bora_attention_arch_v5.png", dpi=400, bbox_inches="tight", facecolor="white")
fig.savefig("bora_attention_arch_v5.pdf", bbox_inches="tight", facecolor="white")
print(f"wrote bora_attention_arch_v5.png / .pdf   [{SRC}]")
