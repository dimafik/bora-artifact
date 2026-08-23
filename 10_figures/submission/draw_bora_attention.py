#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Draw the Multi-Head Self-Attention architecture of the BORA predictor
exactly as described in tnse_submission68.tex, Section III.E
("Predictor (Multi-Head Transformer)") and the scoring pseudocode.

Reference model (the 17,185-parameter instance the body specifies):
  input window  X in R^{L x d},  L = 64 ticks, d = 5 channels
                channels: CC, RTT, Lambda (log-rep lag), lambda (ack rate),
                          tau (vote-grant rate); z-normalised
  embedding     Linear d=5 -> d_model=32, + sinusoidal positional encoding
  encoder       x2 layers, each = MHSA(4 heads) + Add&LN + GELU-FFN + Add&LN
  head          mean-pool over L -> Linear 32 -> 2 logits {benign, risk}
  output        q = softmax(z / temperature);  p_t = q_risk,
                c_t = |q_risk - q_benign|   (confidence = softmax margin)

Panel (a): the full predictor stack.
Panel (b): a zoom of one Multi-Head Self-Attention block
           (Q/K/V projections -> 4 heads -> scaled dot-product attention
            -> concat -> output projection).

Run:  python draw_bora_attention.py
Out:  bora_attention_arch.png  and  bora_attention_arch.pdf
"""

import matplotlib
matplotlib.use("Agg")  # headless: write file without a display
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

# ----- architecture hyper-parameters (from the paper body) -----
L          = 64    # window length (ticks)
D_IN       = 5     # telemetry channels
D_MODEL    = 32    # embedding width
N_HEADS    = 4     # attention heads
D_K        = D_MODEL // N_HEADS   # per-head width = 8
N_LAYERS   = 2     # encoder layers
N_CLASSES  = 2     # {benign, risk}
N_PARAMS   = "17,185"

# ----- colour palette -----
C_INPUT = "#dbeafe"; E_INPUT = "#2563eb"
C_EMB   = "#e0e7ff"; E_EMB   = "#4f46e5"
C_ATTN  = "#fde68a"; E_ATTN  = "#d97706"
C_FFN   = "#bbf7d0"; E_FFN   = "#059669"
C_NORM  = "#f3f4f6"; E_NORM  = "#6b7280"
C_HEAD  = "#fbcfe8"; E_HEAD  = "#db2777"
C_OUT   = "#fecaca"; E_OUT   = "#dc2626"
C_QKV   = "#cffafe"; E_QKV   = "#0891b2"


def box(ax, xy, w, h, text, fc, ec, fs=10, lw=1.6, style="round,pad=0.02,rounding_size=0.06"):
    x, y = xy
    p = FancyBboxPatch((x, y), w, h, boxstyle=style,
                       facecolor=fc, edgecolor=ec, linewidth=lw, zorder=2)
    ax.add_patch(p)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fs, zorder=3)
    return (x + w / 2, y)          # bottom-centre


def bottom(b): return b
def top(xy, h): return (xy[0], xy[1] + h)


def arrow(ax, p0, p1, color="#374151", lw=1.7, style="-|>", rad=0.0):
    a = FancyArrowPatch(p0, p1, arrowstyle=style, mutation_scale=14,
                        lw=lw, color=color, zorder=1,
                        connectionstyle=f"arc3,rad={rad}")
    ax.add_patch(a)


# =====================================================================
fig = plt.figure(figsize=(15, 9.5))
gs = fig.add_gridspec(1, 2, width_ratios=[1.0, 1.35], wspace=0.12)
axL = fig.add_subplot(gs[0, 0]); axR = fig.add_subplot(gs[0, 1])
for ax in (axL, axR):
    ax.set_xlim(0, 10); ax.set_ylim(0, 13)
    ax.axis("off")

# ---------------------------------------------------------------------
# Panel (a): full predictor stack  (bottom -> top)
# ---------------------------------------------------------------------
axL.set_title("(a) BORA predictor  (two-layer Multi-Head Transformer, "
              f"{N_PARAMS} params)", fontsize=11, weight="bold")

cx, w = 2.7, 4.6
y = 0.4

# input
b_in = box(axL, (cx, y), w, 1.15,
           f"Telemetry window  X $\\in\\mathbb{{R}}^{{L\\times d}}$ = {L}$\\times${D_IN}\n"
           "channels: CC, RTT, $\\Lambda$, $\\lambda$, $\\tau$  (z-normalised)",
           C_INPUT, E_INPUT, fs=9.5)
top_in = (cx + w / 2, y + 1.15)

# embedding + positional encoding
y = 2.15
b_emb = box(axL, (cx, y), w, 1.05,
            f"Input embedding: Linear  {D_IN} $\\to$ $d_{{model}}$={D_MODEL}\n"
            f"+ positional encoding (L={L})",
            C_EMB, E_EMB, fs=9.5)
arrow(axL, top_in, (cx + w / 2, y))
top_emb = (cx + w / 2, y + 1.05)

# encoder layers (x2) drawn as a stacked block
y = 3.7
enc_h = 5.1
# outer dashed container
axL.add_patch(FancyBboxPatch((cx - 0.35, y - 0.2), w + 0.7, enc_h + 0.4,
              boxstyle="round,pad=0.02,rounding_size=0.05",
              facecolor="none", edgecolor="#9ca3af", linewidth=1.4,
              linestyle=(0, (6, 4)), zorder=1))
axL.text(cx - 0.15, y + enc_h + 0.05, f"Encoder  $\\times$ {N_LAYERS} layers",
         fontsize=10, weight="bold", color="#374151")

# inside one layer: MHSA -> Add&LN -> FFN -> Add&LN
iy = y + 0.1
b_attn = box(axL, (cx, iy), w, 1.1,
             f"Multi-Head Self-Attention\n({N_HEADS} heads, head dim "
             f"$d_k$={D_K})   $\\Rightarrow$ see (b)",
             C_ATTN, E_ATTN, fs=9.5)
arrow(axL, top_emb, (cx + w / 2, iy))
iy2 = iy + 1.35
b_n1 = box(axL, (cx + 0.8, iy2), w - 1.6, 0.6, "Add & LayerNorm", C_NORM, E_NORM, fs=9)
arrow(axL, (cx + w / 2, iy + 1.1), (cx + w / 2, iy2))
iy3 = iy2 + 0.95
b_ffn = box(axL, (cx, iy3), w, 1.0,
            f"Position-wise FFN\n(Linear {D_MODEL}$\\to$FF$\\to${D_MODEL}, GELU)",
            C_FFN, E_FFN, fs=9.5)
arrow(axL, (cx + w / 2, iy2 + 0.6), (cx + w / 2, iy3))
iy4 = iy3 + 1.25
b_n2 = box(axL, (cx + 0.8, iy4), w - 1.6, 0.6, "Add & LayerNorm", C_NORM, E_NORM, fs=9)
arrow(axL, (cx + w / 2, iy3 + 1.0), (cx + w / 2, iy4))
top_enc = (cx + w / 2, y + enc_h + 0.2)
arrow(axL, (cx + w / 2, iy4 + 0.6), top_enc, rad=0.0)

# pooling
y = 9.35
b_pool = box(axL, (cx + 0.6, y), w - 1.2, 0.8,
             f"Mean-pool over L $\\to$ $\\mathbb{{R}}^{{{D_MODEL}}}$",
             C_EMB, E_EMB, fs=9.5)
arrow(axL, top_enc, (cx + w / 2, y))
top_pool = (cx + w / 2, y + 0.8)

# classification head
y = 10.45
b_cls = box(axL, (cx + 0.4, y), w - 0.8, 0.85,
            f"Linear {D_MODEL} $\\to$ {N_CLASSES} logits\n"
            "{benign, risk}",
            C_HEAD, E_HEAD, fs=9.5)
arrow(axL, top_pool, (cx + w / 2, y))
top_cls = (cx + w / 2, y + 0.85)

# output (temperature softmax)
y = 11.7
b_out = box(axL, (cx + 0.2, y), w - 0.4, 1.05,
            "$q=\\mathrm{softmax}(z/\\mathrm{temp})$\n"
            "$p_t=q_{risk}$,   $c_t=|q_{risk}-q_{benign}|$",
            C_OUT, E_OUT, fs=9.5)
arrow(axL, top_cls, (cx + w / 2, y))

# ---------------------------------------------------------------------
# Panel (b): Multi-Head Self-Attention zoom
# ---------------------------------------------------------------------
axR.set_title("(b) Multi-Head Self-Attention  "
              f"($d_{{model}}$={D_MODEL}, h={N_HEADS} heads, $d_k$={D_K})",
              fontsize=11, weight="bold")

# input sequence
b_h = box(axR, (3.4, 0.4), 3.2, 0.95,
          f"H $\\in\\mathbb{{R}}^{{L\\times d_{{model}}}}$ = {L}$\\times${D_MODEL}\n(embedded tokens)",
          C_EMB, E_EMB, fs=9.5)
top_h = (5.0, 1.35)

# Q K V projections
qkv_y = 2.1
xs = [1.2, 4.0, 6.8]
labels = ["Q = H$W_Q$", "K = H$W_K$", "V = H$W_V$"]
qkv_tops = []
for x, lab in zip(xs, labels):
    box(axR, (x, qkv_y), 2.0, 0.85, lab + f"\n$\\mathbb{{R}}^{{{L}\\times{D_MODEL}}}$",
        C_QKV, E_QKV, fs=9.5)
    arrow(axR, top_h, (x + 1.0, qkv_y), rad=0.0)
    qkv_tops.append((x + 1.0, qkv_y + 0.85))

# split into heads label
axR.text(5.0, 3.25, f"split into {N_HEADS} heads  (each $d_k$={D_K})",
         ha="center", fontsize=9.5, style="italic", color="#374151")

# per-head scaled dot-product attention (show heads 1 and 4, ellipsis)
head_y = 3.7
head_boxes_x = [0.7, 3.05, 5.4, 7.75]
for hi, hx in enumerate(head_boxes_x):
    fc = C_ATTN if hi in (0, N_HEADS - 1) else "#fef3c7"
    box(axR, (hx, head_y), 1.9, 2.05,
        f"head {hi+1}\n\n"
        f"$A_i=\\mathrm{{softmax}}\\!\\left(\\dfrac{{Q_iK_i^\\top}}{{\\sqrt{{d_k}}}}\\right)$\n"
        f"$\\in\\mathbb{{R}}^{{{L}\\times{L}}}$\n\n"
        f"$\\mathrm{{head}}_i=A_iV_i$\n$\\in\\mathbb{{R}}^{{{L}\\times{D_K}}}$",
        fc, E_ATTN, fs=8.2)
    # feed Q,K,V into each head
    for qt in qkv_tops:
        arrow(axR, qt, (hx + 0.95, head_y), lw=0.8, rad=0.06, style="-|>")

# concat
cat_y = 6.4
b_cat = box(axR, (2.7, cat_y), 4.6, 0.85,
            f"Concat heads  $\\to\\mathbb{{R}}^{{L\\times d_{{model}}}}$ = {L}$\\times${D_MODEL}",
            C_FFN, E_FFN, fs=9.5)
for hx in head_boxes_x:
    arrow(axR, (hx + 0.95, head_y + 2.05), (5.0, cat_y), lw=1.0, rad=0.0)

# output projection
proj_y = 7.7
b_proj = box(axR, (3.2, proj_y), 3.6, 0.85,
             "Output projection  $\\cdot W_O$\n"
             f"$\\to\\mathbb{{R}}^{{{L}\\times{D_MODEL}}}$",
             C_QKV, E_QKV, fs=9.5)
arrow(axR, (5.0, cat_y + 0.85), (5.0, proj_y))

# residual + LN note
ln_y = 9.0
b_ln = box(axR, (3.4, ln_y), 3.2, 0.7,
           "Add (residual) & LayerNorm", C_NORM, E_NORM, fs=9.5)
arrow(axR, (5.0, proj_y + 0.85), (5.0, ln_y))
arrow(axR, top_h, (2.7, ln_y + 0.35), lw=1.0, rad=-0.55, style="-|>")  # residual skip
axR.text(1.5, 6.4, "residual\nskip", ha="center", fontsize=8.5,
         color="#6b7280", style="italic")

# scaled dot-product attention formula caption
axR.text(5.0, 10.2,
         r"$\mathrm{Attention}(Q,K,V)=\mathrm{softmax}\!\left(QK^\top/\sqrt{d_k}\right)V$",
         ha="center", fontsize=11)
axR.text(5.0, 10.75,
         r"$\mathrm{MHSA}(H)=\mathrm{Concat}(\mathrm{head}_1,\dots,\mathrm{head}_4)\,W_O$",
         ha="center", fontsize=11)

fig.suptitle("BORA predictor: Multi-Head Self-Attention architecture "
             "(tnse_submission68.tex, Sec. III.E)",
             fontsize=13, weight="bold", y=0.99)

fig.savefig("bora_attention_arch.png", dpi=200, bbox_inches="tight")
fig.savefig("bora_attention_arch.pdf", bbox_inches="tight")
print("wrote bora_attention_arch.png and bora_attention_arch.pdf")
