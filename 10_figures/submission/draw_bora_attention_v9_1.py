#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
BORA predictor - detailed Multi-Head Self-Attention architecture (v9).
A richer, more complex rendering than v8, still 100% faithful to
tnse_submission68.tex (Sec. III.B telemetry, Sec. III.E predictor,
Algorithm 1 advisor, Def. per-orderer risk score, the TinyTransformer code).

Content (all body-grounded):
  Row A  full pipeline: telemetry 64x5 -> z-normalise -> Linear embedding ->
         sinusoidal positional encoding -> Transformer encoder x2 ->
         mean-pool (R^32) -> risk head -> temperature softmax (p_t, c_t) ->
         BORA advisor (Algorithm 1) -> bounded blacklist B_t (|B_t|<f).
  Row B  three detail panels:
         (1) one encoder layer (x2): MHSA + Add&Norm, FFN(GELU) + Add&Norm,
             with residual skips;
         (2) multi-head self-attention mechanism: Q,K,V -> split 4 heads
             (d_model 32 = 4 x d_k 8) -> scaled dot-product attention
             (MatMul, Scale 1/sqrt(d_k), SoftMax, MatMul) -> Concat -> Linear;
         (3) BORA advisor Algorithm 1 steps (a)-(d) -> B_t, with the
             fail-open counter K_fail=3 and monotone sequence s_t.
  Row C  four head-specialization maps (Local / Baseline / Periodic[heartbeat]
         / Onset) with Query/Key/V axes.

If attn_real.npy ([4,n,n]) exists it is used for the head maps.
Run:  python draw_bora_attention_v9.py
"""
import os, numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle, Wedge, Circle
import matplotlib.patheffects as pe

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8.5})

INK, SLATE = "#1f2937", "#5b6878"
PANEL = ("#f7f9fc", "#c2ccd9"); HEAD_BAR = "#27364b"
INDIGO = ("#e9e9fb", "#5b5bd6"); AMBER = ("#fdebc4", "#cf8616")
GREEN = ("#d6f0df", "#1f9d57"); GREY = ("#eef1f5", "#8a97a6")
RED = ("#fde2e2", "#d23b3b"); CYAN = ("#d9f3f7", "#118a9e")
OPC = ("#fff1d6", "#cf8616"); ADDC = ("#e6eef9", "#3b6db3")
ACMAP = "viridis"
SH = pe.withSimplePatchShadow(offset=(1.1, -1.1), alpha=0.10)
CH = [("CC", "commit contribution"), ("RTT", "round-trip time"),
      (r"$\Lambda$", "log-replication lag"), (r"$\lambda$", "ack rate"),
      (r"$\tau$", "vote-grant rate")]
HCOL = ["#cf8616", "#1f8e85", "#5b5bd6", "#cf5f7e"]
ROLE_T = ["Head 1: Local", "Head 2: Baseline", "Head 3: Periodic", "Head 4: Onset"]
ROLE_D = ["nearby ticks (fast AR(1) change)", "distant ticks (slow trend)",
          "regular intervals (heartbeat)", "attack-onset tick (anomaly)"]


def rbox(ax, x, y, w, h, col, t="", fs=8.5, lw=1.2, bold=False, shadow=True, rd=0.06):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={rd}",
                 facecolor=col[0], edgecolor=col[1], linewidth=lw, zorder=4,
                 path_effects=[SH] if shadow else None))
    if t:
        ax.text(x+w/2, y+h/2, t, ha="center", va="center", fontsize=fs, color=INK,
                weight="bold" if bold else "normal", zorder=6)


def panel(ax, x, y, w, h, title, tfs=9.5):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.015",
                 facecolor=PANEL[0], edgecolor=PANEL[1], linewidth=1.4, zorder=2, path_effects=[SH]))
    ax.add_patch(FancyBboxPatch((x, y+h-2.7), w, 2.7, boxstyle="round,pad=0,rounding_size=0.015",
                 facecolor=HEAD_BAR, edgecolor=HEAD_BAR, zorder=3))
    ax.text(x+w/2, y+h-1.35, title, ha="center", va="center", color="white",
            fontsize=tfs, weight="bold", zorder=5)


def arr(ax, p0, p1, lw=1.5, color=SLATE, rad=0.0, lab="", fs=7, style="-|>"):
    ax.add_patch(FancyArrowPatch(p0, p1, arrowstyle=style, mutation_scale=11, lw=lw, color=color,
                 zorder=5, shrinkA=2, shrinkB=2, connectionstyle=f"arc3,rad={rad}"))
    if lab:
        ax.text((p0[0]+p1[0])/2, (p0[1]+p1[1])/2+1.1, lab, ha="center", fontsize=fs, color=SLATE,
                zorder=7, bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none", alpha=.9))


def oplus(ax, x, y, r=1.1, z=6):
    ax.add_patch(Circle((x, y), r, facecolor="white", edgecolor=ADDC[1], lw=1.4, zorder=z))
    ax.text(x, y, "+", ha="center", va="center", fontsize=10, color=ADDC[1], weight="bold", zorder=z+1)


def amap(ax, x, y, w, h, A, ec, z=8):
    ax.imshow(A/(A.max()+1e-9), extent=[x, x+w, y, y+h], origin="lower", cmap=ACMAP,
              aspect="auto", zorder=z)
    ax.add_patch(Rectangle((x, y), w, h, fill=False, edgecolor=ec, lw=1.3, zorder=z+1))


def stacked(ax, x, y, w, h, n=3, dx=0.9, dy=0.9, fc="#e3ecf7", ec=SLATE, z=4):
    for i in range(n-1, -1, -1):
        ax.add_patch(FancyBboxPatch((x+i*dx, y-i*dy), w, h, boxstyle="round,pad=0,rounding_size=0.1",
                     facecolor=fc, edgecolor=ec, lw=1.0, zorder=z+(n-i)))


def patterns(n=64):
    ii, jj = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
    onset = int(n*0.72)
    P = [np.exp(-((ii-jj)**2)/8.0), np.exp(-((ii-jj)**2)/600.0)+0.12,
         0.5+0.5*np.cos((ii-jj)*2*np.pi/6.0), np.exp(-((jj-onset)**2)/12.0)+0.03]
    return [p/p.sum(axis=1, keepdims=True) for p in P]


real = None
if os.path.exists("attn_real.npy"):
    a = np.load("attn_real.npy")
    if a.ndim == 3 and a.shape[0] >= 4:
        real = [a[i] for i in range(4)]
maps = real if real is not None else patterns()
SRC = "real trained weights" if real is not None else "representative attention (illustrative)"

# =====================================================================
fig = plt.figure(figsize=(18, 11.2)); fig.patch.set_facecolor("white")
ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 200); ax.set_ylim(0, 124); ax.axis("off")

# =================== ROW A: full pipeline ===================
yA, hA = 110, 8.5
steps = [
    (WHITE := ("white", INK), "Telemetry\n$64\\times5$"),
    (CYAN, "z-normalise"),
    (INDIGO, "Linear\nembedding"),
    (INDIGO, "Positional\nencoding"),
    (AMBER, "Transformer\nencoder $\\times 2$"),
    (GREEN, "Mean-pool\n$\\rightarrow \\mathbb{R}^{32}$"),
    (RED, "Risk head\n$\\rightarrow 2$ logits"),
    (RED, "Temperature\nsoftmax"),
    (GREY, "BORA advisor\n(Algorithm 1)"),
    (CYAN, "$\\mathcal{B}_t$\n$|\\mathcal{B}_t|<f$"),
]
sw, gap = 16.5, 3.0
x0 = 4
xc = []
for i, (col, t) in enumerate(steps):
    x = x0 + i*(sw+gap)
    rbox(ax, x, yA, sw, hA, col, t, fs=7.4, bold=(col is AMBER or col is GREY))
    xc.append(x+sw/2)
    if i > 0:
        lab = {1: r"$64\times5$", 2: "", 3: r"$64\times32$", 4: r"$64\times32$",
               5: r"$64\times32$", 6: r"$32$", 7: r"$2$", 8: r"$p_t,c_t$", 9: ""}.get(i, "")
        arr(ax, (x-gap-0.2, yA+hA/2), (x, yA+hA/2), lab=lab, fs=6.4)
ax.text(xc[7], yA-2.3, r"$p_t=q_{\mathrm{risk}}$,  $c_t=|q_{\mathrm{risk}}-q_{\mathrm{benign}}|$",
        ha="center", fontsize=6.8, color=SLATE)
ax.text(xc[0], yA-2.3, r"channels: CC, RTT, $\Lambda$, $\lambda$, $\tau$",
        ha="center", fontsize=6.4, color=SLATE)
ax.text(xc[4], yA+hA+2.0, "$d_{\\mathrm{model}}{=}32$, 4 heads, $d_k{=}8$, 17,185 params",
        ha="center", fontsize=7.2, weight="bold", color=AMBER[1])
fig.text(0.5, 0.987, "BORA predictor - detailed Multi-Head Self-Attention over a 5-channel telemetry time series",
         ha="center", fontsize=15, weight="bold", color=INK)

# callouts to row-B panels
for sx, tx in [(xc[4], 33), (xc[4], 100), (xc[8], 168)]:
    ax.add_patch(FancyArrowPatch((sx, yA), (tx, 96.5), arrowstyle="-", lw=0.9,
                 color="#aab4c2", linestyle=(0, (3, 3)), zorder=1))

# =================== ROW B: three detail panels ===================
# ---- B1: encoder layer internals ----
panel(ax, 2, 50, 62, 46, "Transformer encoder layer  (x2)")
cxm = 33
rbox(ax, cxm-7, 52.5, 14, 5.5, INDIGO, "input  $64\\times32$", fs=7)
yv = 60
rbox(ax, cxm-13, yv, 26, 6.5, AMBER, "Multi-Head\nSelf-Attention", fs=8, bold=True)
arr(ax, (cxm, 58), (cxm, yv))
oplus(ax, cxm, yv+9.6); arr(ax, (cxm, yv+6.5), (cxm, yv+8.5))
ax.add_patch(FancyArrowPatch((cxm-13, 55.2), (cxm-2.6, yv+9.6), arrowstyle="-|>", mutation_scale=10,
             lw=1.2, color=ADDC[1], zorder=5, connectionstyle="arc3,rad=-0.5"))
ax.text(cxm-16, 66, "residual", rotation=90, fontsize=6, color=ADDC[1], style="italic")
rbox(ax, cxm-12, yv+12.5, 24, 4.6, GREY, "Add & LayerNorm", fs=7.4)
arr(ax, (cxm, yv+10.7), (cxm, yv+12.5))
yf = yv+19
rbox(ax, cxm-13, yf, 26, 6.0, GREEN, "Feed-Forward\n(GELU)", fs=8)
arr(ax, (cxm, yv+17.1), (cxm, yf))
oplus(ax, cxm, yf+9.2); arr(ax, (cxm, yf+6.0), (cxm, yf+8.1))
ax.add_patch(FancyArrowPatch((cxm-13, yf+2.5), (cxm-2.6, yf+9.2), arrowstyle="-|>", mutation_scale=10,
             lw=1.2, color=ADDC[1], zorder=5, connectionstyle="arc3,rad=-0.5"))
rbox(ax, cxm-12, yf+12.0, 24, 4.6, GREY, "Add & LayerNorm", fs=7.4)
arr(ax, (cxm, yf+10.3), (cxm, yf+12.0))
ax.text(cxm+20, 72, "stacked\n$\\times 2$", ha="center", fontsize=7.5, weight="bold", color=AMBER[1])

# ---- B2: multi-head self-attention mechanism ----
panel(ax, 66, 50, 68, 46, "Multi-Head Self-Attention mechanism")
bx = 70
rbox(ax, bx, 52.5, 16, 5.0, INDIGO, "H  $64\\times32$", fs=7)
for j, nm in enumerate(["Q", "K", "V"]):
    rbox(ax, bx+0.5+j*6.5, 60, 5.5, 4.6, CYAN, nm, fs=8.5, bold=True, shadow=False)
    arr(ax, (bx+8, 57.5), (bx+3.2+j*6.5, 60), lw=0.8)
ax.text(bx+10, 66.4, "linear $Q,K,V$  ($64\\times32$)", fontsize=6.6, color=SLATE)
# split heads bar
rbox(ax, bx, 69.5, 22, 0.1, ("white", "white"), shadow=False)
for k in range(4):
    rbox(ax, bx+k*5.6, 69, 5.0, 3.8, (HCOL[k]+"22" if False else ("#f3f1ea", HCOL[k])),
         f"h{k+1}", fs=6.6, bold=True, shadow=False, lw=1.1)
ax.text(bx+11, 73.8, r"split: $d_{\mathrm{model}}{=}32 = 4 \times d_k{=}8$", ha="center",
        fontsize=6.8, color=INK)
arr(ax, (bx+8, 64.6), (bx+11, 69))
# scaled dot-product attention op-column (per head)
ox = bx+30
ax.add_patch(FancyBboxPatch((ox-2, 58.5), 22, 33, boxstyle="round,pad=0,rounding_size=0.04",
             facecolor="#fffaf0", edgecolor=AMBER[1], lw=1.2, linestyle=(0, (4, 3)), zorder=3))
ax.text(ox+9, 90.0, "Scaled Dot-Product\nAttention  (per head)", ha="center", fontsize=7.2,
        weight="bold", color=AMBER[1])
ops = [("MatMul  $Q\\,K^{\\top}$", 60.5), (r"Scale  $\div\sqrt{d_k}$", 66.0),
       ("SoftMax", 71.5), (r"MatMul  $\cdot\,V$", 77.0)]
for t, yy in ops:
    rbox(ax, ox, yy, 18, 4.0, OPC, t, fs=7.2)
for a, b in [(60.5, 66.0), (66.0, 71.5), (71.5, 77.0)]:
    arr(ax, (ox+9, a+4.0), (ox+9, b), lw=1.2)
arr(ax, (bx+11, 72.8), (ox, 62.5), lw=1.0, rad=0.1)        # Q,K -> first MatMul
arr(ax, (bx+11.5, 64.6), (ox, 79.0), lw=1.0, rad=-0.45)    # V -> last MatMul
# concat + linear
rbox(ax, ox, 83.0, 18, 4.4, GREEN, "Concat 4 heads  $64\\times32$", fs=6.8)
arr(ax, (ox+9, 81.0), (ox+9, 83.0))
ax.text(ox+9, 56.6, r"$\times\,4$ heads in parallel", ha="center", fontsize=6.6,
        style="italic", color=SLATE)

# ---- B3: BORA advisor Algorithm 1 ----
panel(ax, 136, 50, 62, 46, "BORA advisor  (Algorithm 1)")
bx3, bw3 = 141, 50
steps_alg = [
    (r"(a) confidence filter:  $c_t^{(i)} \geq \theta_{\mathrm{conf}}$", GREY),
    (r"(b) risk filter:  $p_t^{(i)} \geq \theta_{\mathrm{risk}}$", GREY),
    (r"(c) hard cap:  $|\mathcal{B}_t| < f - r$", AMBER),
    (r"(d) fail-open:  $K \geq K_{\mathrm{fail}}{=}3 \Rightarrow \mathcal{B}_t{=}\emptyset$", GREY),
]
cx3 = bx3 + bw3/2
rbox(ax, bx3, 86.5, bw3, 5.0, RED, r"per-orderer  $(p_t^{(i)}, c_t^{(i)})$", fs=7.4)
yy = 79.5
for t, col in steps_alg:
    rbox(ax, bx3, yy, bw3, 5.2, col, t, fs=7.0, bold=(col is AMBER))
    yy -= 7.0
arr(ax, (cx3, 86.5), (cx3, 84.7))
for a in range(3):
    arr(ax, (cx3, 79.5-a*7.0), (cx3, 79.5-a*7.0-1.8))
rbox(ax, bx3+7, 53.5, bw3-14, 5.6, CYAN, r"emit  $\{\mathcal{B}_t,\ s_t{=}s_{t-1}{+}1\}$", fs=6.8, bold=True)
arr(ax, (cx3, yy+7.0), (cx3, 59.1))
ax.text(cx3, 51.6, r"monotone seq.\ $s_t$ guards UDS replay", ha="center", fontsize=6.2,
        color=SLATE, style="italic")

# =================== ROW C: head specialization ===================
panel(ax, 2, 2, 196, 42, "Insight: Interpretable Attention-Head Specialization "
      "(complementary patterns over the 64-tick sequence)")
for k in range(4):
    cx = 11 + k*48
    ax.text(cx+16, 34.5, ROLE_T[k], ha="center", fontsize=10, weight="bold", color=HCOL[k], zorder=9)
    amap(ax, cx, 9, 32, 23, maps[k], HCOL[k], z=8)
    ax.text(cx+16, 6.6, ROLE_D[k], ha="center", fontsize=7.6, color=SLATE, zorder=9)
    ax.text(cx-1.8, 23, "Query", rotation=90, ha="center", va="center", fontsize=7, color=INK, zorder=9)
    ax.text(cx-1.8, 14.5, "Key", rotation=90, ha="center", va="center", fontsize=7, color=INK, zorder=9)
    ax.text(cx+33.6, 20.5, "V", rotation=90, ha="center", va="center", fontsize=7.8, weight="bold", color=INK, zorder=9)

ax.text(197.5, 0.6, SRC, ha="right", fontsize=6.2, color="#9aa6b2", style="italic")

fig.savefig("bora_attention_arch_v9_1.png", dpi=240, bbox_inches="tight", facecolor="white")
fig.savefig("bora_attention_arch_v9_1.pdf", bbox_inches="tight", facecolor="white")
print(f"wrote bora_attention_arch_v9_1.png / .pdf   [{SRC}]")
