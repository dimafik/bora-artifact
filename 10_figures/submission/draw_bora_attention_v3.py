#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BORA predictor - Multi-Head Self-Attention architecture (detailed, no equations).

Publication-style figure. Every step is shown explicitly with tensor SHAPES
only (no formulas). The multi-head block makes clear *what the 4 heads are*:
the 32-d embedding is split into 4 disjoint 8-d sub-spaces, and each head runs
its own attention across all 64 time ticks of the telemetry window.

Faithful to tnse_submission68.tex Sec. III.E (reference 17,185-param model):
    window 64 x 5 -> Linear+PosEnc 64 x 32 -> Encoder x2
    [ Multi-Head Self-Attention(4 heads, d_k=8) + Add&Norm + FFN(GELU) + Add&Norm ]
    -> temporal mean-pool 32 -> risk head 2 -> (risk p_t, confidence c_t)

Run:  python draw_bora_attention_v3.py
Out:  bora_attention_arch_v3.png / .pdf
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
INDIGO = ("#eaeafb", "#5b5bd6")
AMBER  = ("#fdebc4", "#cf8616")
GREEN  = ("#dcf3e3", "#1f9d57")
GREY   = ("#eef1f5", "#9aa6b2")
RED    = ("#fde2e2", "#d23b3b")
CYAN   = ("#d9f3f7", "#118a9e")
WHITE  = ("white", INK)
HEADC  = [("#fbe3b0", "#cf8616"), ("#cdeeea", "#1f8e85"),
          ("#dcd9f7", "#5b5bd6"), ("#f6d6df", "#cf5f7e")]
SHADOW = pe.withSimplePatchShadow(offset=(1.3, -1.3), alpha=0.12)


def rbox(ax, x, y, w, h, col, text="", fs=10, lw=1.5, bold=False, shadow=True,
         rd=0.04, tcol=INK):
    ax.add_patch(FancyBboxPatch((x, y), w, h,
                 boxstyle=f"round,pad=0,rounding_size={rd}",
                 facecolor=col[0], edgecolor=col[1], linewidth=lw, zorder=3,
                 path_effects=[SHADOW] if shadow else None))
    if text:
        ax.text(x+w/2, y+h/2, text, ha="center", va="center", fontsize=fs,
                color=tcol, weight="bold" if bold else "normal", zorder=5)


def conn(ax, p0, p1, label="", lw=1.7, rad=0.0, fs=8.5, color=SLATE,
         style="-|>", loff=(0, 1.0)):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle=style, mutation_scale=14,
                 lw=lw, color=color, zorder=2, shrinkA=2, shrinkB=2,
                 connectionstyle=f"arc3,rad={rad}"))
    if label:
        ax.text((p0[0]+p1[0])/2+loff[0], (p0[1]+p1[1])/2+loff[1], label,
                ha="center", va="center", fontsize=fs, color=SLATE, zorder=6,
                bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=.9))


def grid(ax, x, y, w, h, nr, nc, data, cmap, ec="white", lw=0.4, z=4):
    cw, ch = w/nc, h/nr
    for i in range(nr):
        for j in range(nc):
            ax.add_patch(Rectangle((x+j*cw, y+(nr-1-i)*ch), cw, ch,
                         facecolor=cmap(data[i, j]), edgecolor=ec, lw=lw, zorder=z))


fig = plt.figure(figsize=(15.5, 9.6))
ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 155); ax.set_ylim(0, 96)
ax.axis("off")

# =====================================================================
#  TOP: end-to-end pipeline (compact, shapes on arrows)
# =====================================================================
yT, hT = 84, 8.5
rbox(ax, 3, yT, 16, hT, WHITE, "Per-orderer\ntelemetry", fs=9.5)
ax.text(11, yT-2.0, r"$64\times5$", ha="center", fontsize=8.5, color=SLATE)
rbox(ax, 24, yT, 15, hT, INDIGO, "Linear embed\n+ pos. enc.", fs=9.5)
conn(ax, (19, yT+hT/2), (24, yT+hT/2), r"$64\times5$")
# encoder container (taller)
ecx, ecw = 44, 19
ax.add_patch(FancyBboxPatch((ecx-1.5, yT-4), ecw+3, hT+8,
             boxstyle="round,pad=0,rounding_size=0.04", facecolor="#fbfaf6",
             edgecolor=AMBER[1], lw=1.5, linestyle=(0, (5, 3)), zorder=2,
             path_effects=[SHADOW]))
ax.text(ecx+ecw/2, yT+hT+4.3, r"Transformer encoder $\times2$", ha="center",
        fontsize=9.5, weight="bold", color=AMBER[1])
rbox(ax, ecx, yT+hT-3.2, ecw, 3.0, AMBER, "Multi-Head Self-Attn", fs=8.2, bold=True, lw=1.2)
rbox(ax, ecx, yT+hT-6.6, ecw, 3.0, GREEN, "Feed-Forward (GELU)", fs=8.2, lw=1.2)
mhsa_anchor = (ecx+ecw/2, yT+hT-3.2)
conn(ax, (39, yT+hT/2), (ecx-1.5, yT+hT/2), r"$64\times32$")
rbox(ax, 68, yT, 13, hT, INDIGO, "Temporal\nmean-pool", fs=9.5)
conn(ax, (ecx+ecw+1.5, yT+hT/2), (68, yT+hT/2), r"$64\times32$")
rbox(ax, 86, yT, 11, hT, RED, "Risk head", fs=9.5)
conn(ax, (81, yT+hT/2), (86, yT+hT/2), r"$32$")
rbox(ax, 102, yT+hT-3.6, 15, 3.4, RED, r"risk  $p_t$", fs=9, bold=True)
rbox(ax, 102, yT-0.2, 15, 3.4, CYAN, r"confidence  $c_t$", fs=9, bold=True)
conn(ax, (97, yT+hT/2), (102, yT+hT-1.9), rad=.2)
conn(ax, (97, yT+hT/2), (102, yT+1.5), rad=-.2, label=r"$2$")
ax.text(127, yT+hT/2, r"$\Rightarrow\ \mathcal{B}_t$  (BORA advisor)", ha="left",
        va="center", fontsize=9.5, color=INK, weight="bold")

# =====================================================================
#  BOTTOM: Multi-Head Self-Attention detail (no equations)
# =====================================================================
ax.add_patch(FancyBboxPatch((3, 4), 149, 68,
             boxstyle="round,pad=0,rounding_size=0.012", facecolor="#fffdf8",
             edgecolor=AMBER[1], lw=1.5, linestyle=(0, (4, 3)), zorder=1,
             path_effects=[SHADOW]))
ax.text(6, 69.5, "Inside one Multi-Head Self-Attention block   "
        r"($d_{\mathrm{model}}=32$  $\rightarrow$  $h=4$ heads  $\times$  $d_k=8$)",
        fontsize=11.5, weight="bold", color=AMBER[1])
# dashed callout from top MHSA bar
ax.add_patch(FancyArrowPatch(mhsa_anchor, (60, 72), arrowstyle="-", lw=1.0,
             color=AMBER[1], linestyle=(0, (3, 3)), zorder=1))

# --- A. embedded sequence (time x feature) ---
ax.text(16, 64.5, "embedded sequence", ha="center", fontsize=9.5, weight="bold", color=INK)
rng = np.add.outer(np.linspace(0, 1, 8), np.linspace(0, 1, 16))
seq = 0.25 + 0.5*np.abs(np.sin(rng*3))
seq[5:, 11:] = 0.9
grid(ax, 8, 40, 16, 20, 8, 16, seq, plt.cm.Blues, z=4)
ax.add_patch(Rectangle((8, 40), 16, 20, fill=False, edgecolor=INK, lw=1.5, zorder=6))
ax.text(16, 38.0, r"$64$ ticks $\times$ $32$", ha="center", fontsize=8.5, color=SLATE)
ax.text(5.7, 50, "time (64)", rotation=90, ha="center", va="center", fontsize=8, color=SLATE)
ax.text(16, 61.4, "32 features", ha="center", fontsize=8, color=SLATE)

# --- B. Q,K,V projections ---
qx = 31
for j, nm in enumerate(["Q", "K", "V"]):
    yy = 53.5 - j*7.0
    rbox(ax, qx, yy, 10, 5.4, CYAN, nm, fs=11, bold=True)
    ax.text(qx+5, yy-1.4, r"$64\times32$", ha="center", fontsize=7.6, color=SLATE)
    conn(ax, (24, 50), (qx, yy+2.7), rad=0.05, color=SLATE)
ax.text(qx+5, 60.0, "linear\nprojections", ha="center", fontsize=8.6, color=INK)

# --- C. split feature dim into 4 heads (the key explainer) ---
sx, sw = 47, 22
ax.text(sx+sw/2, 64.5, "split the 32-d embedding into 4 heads",
        ha="center", fontsize=9.5, weight="bold", color=INK)
seg = sw/N_HEADS
for k in range(N_HEADS):
    rbox(ax, sx+k*seg, 55.5, seg-0.5, 5.0, HEADC[k], f"head {k+1}", fs=8.4,
         bold=True, lw=1.3, shadow=False)
# brace + annotation
ax.annotate("", xy=(sx, 54.4), xytext=(sx+sw, 54.4),
            arrowprops=dict(arrowstyle="-", lw=1.2, color=SLATE,
                            connectionstyle="bar,fraction=-0.06"))
ax.text(sx+sw/2, 51.0, r"each head: an $8$-d sub-space  ($4\times8=32$)",
        ha="center", fontsize=8.6, color=SLATE)
ax.text(sx+sw/2, 48.3, "(same split applied to Q, K and V)",
        ha="center", fontsize=8.2, color=SLATE, style="italic")
conn(ax, (qx+10, 50), (sx, 58.0), rad=0.0, color=SLATE, label="")

# --- D. per-head attention: head 1 expanded, heads 2-4 stacked behind ---
ax.text(104, 64.5, "each head attends over all 64 time ticks (independently)",
        ha="center", fontsize=9.5, weight="bold", color=INK)
# stacked ghost planes for heads 4..2 behind
for k in range(N_HEADS-1, 0, -1):
    off = k*1.6
    ax.add_patch(FancyBboxPatch((84+off, 33-off), 40, 24,
                 boxstyle="round,pad=0,rounding_size=0.02",
                 facecolor=HEADC[k][0], edgecolor=HEADC[k][1], lw=1.2, zorder=2+(N_HEADS-k)))
# front plane = head 1
ax.add_patch(FancyBboxPatch((84, 33), 40, 24, boxstyle="round,pad=0,rounding_size=0.02",
             facecolor="#fffaf0", edgecolor=HEADC[0][1], lw=1.6, zorder=7,
             path_effects=[SHADOW]))
ax.text(86, 54.5, "head 1", fontsize=9, weight="bold", color=HEADC[0][1], zorder=9)
# Q1, K1 -> attention map -> xV1 -> head out
rbox(ax, 86, 45.5, 8, 5.0, HEADC[0], r"$Q_1$", fs=10, bold=True, shadow=False, lw=1.2)
rbox(ax, 86, 38.5, 8, 5.0, HEADC[0], r"$K_1$", fs=10, bold=True, shadow=False, lw=1.2)
ax.text(90, 36.7, r"$64\times8$", ha="center", fontsize=7.4, color=SLATE, zorder=9)
# attention matrix heatmap (64x64), near-diagonal + hot band
am = np.fromfunction(lambda i, j: np.exp(-((i-j)**2)/6.0), (10, 10))
am[7:, :] += 0.5
am = am/am.max()
grid(ax, 99, 38, 11, 11, 10, 10, am, plt.cm.YlOrRd, z=8)
ax.add_patch(Rectangle((99, 38), 11, 11, fill=False, edgecolor=INK, lw=1.3, zorder=9))
ax.text(104.5, 50.0, "attention map", ha="center", fontsize=8.2, color=INK, zorder=9)
ax.text(104.5, 36.4, r"$64\times64$ over time", ha="center", fontsize=7.6, color=SLATE, zorder=9)
conn(ax, (94, 48), (99, 46.5), rad=0, color=SLATE)
conn(ax, (94, 41), (99, 40.5), rad=0, color=SLATE)
# x V1 -> head1 output
rbox(ax, 113.5, 41.5, 8.5, 5.0, HEADC[0], r"$V_1$", fs=10, bold=True, shadow=False, lw=1.2)
conn(ax, (110, 43.5), (113.5, 44.0), color=SLATE, label="")
ax.text(118, 39.8, "weighted\nsum", ha="center", fontsize=7.4, color=SLATE, zorder=9)
conn(ax, (124, 45), (130, 45), color=SLATE, label=r"head$_1$ $64\times8$", fs=8, loff=(0, 1.6))

# --- E. concat + F. projection ---
rbox(ax, 130, 33, 12, 10, GREEN, "Concat\n4 heads", fs=9, bold=False)
ax.text(136, 31.0, r"$64\times32$", ha="center", fontsize=7.8, color=SLATE)
for k in range(N_HEADS):
    conn(ax, (124+ (N_HEADS-1-k)*1.6, 45- (N_HEADS-1-k)*1.6), (130, 41-k*1.4),
         lw=1.0, color=HEADC[k][1], rad=0.0)
rbox(ax, 130, 19, 12, 8, CYAN, "Linear\nprojection", fs=9)
conn(ax, (136, 33), (136, 27), color=SLATE, label=r"$64\times32$")
conn(ax, (136, 19), (136, 13), color=SLATE)
ax.text(136, 11.0, "to  Add & Norm", ha="center", fontsize=8.6, color=INK, weight="bold")

# --- legend note ---
ax.add_patch(FancyBboxPatch((8, 9), 70, 9, boxstyle="round,pad=0.3,rounding_size=0.2",
             facecolor="#f4f6fa", edgecolor="#c7d0dc", lw=1.0, zorder=3))
ax.text(9.5, 13.5, "Heads run in parallel on disjoint 8-d sub-spaces of the 32-d "
        "embedding; each learns a different\ntemporal correlation pattern across the "
        "64-tick window. Outputs are concatenated and linearly mixed.",
        fontsize=8.8, color=INK, va="center", zorder=4)

fig.text(0.5, 0.978, "BORA predictor  -  Multi-Head Self-Attention architecture",
         ha="center", fontsize=14, weight="bold", color=INK)

fig.savefig("bora_attention_arch_v3.png", dpi=220, bbox_inches="tight", facecolor="white")
fig.savefig("bora_attention_arch_v3.pdf", bbox_inches="tight", facecolor="white")
print("wrote bora_attention_arch_v3.png / .pdf")
