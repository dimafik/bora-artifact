#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Extract REAL per-head self-attention maps from a trained BORA/TinyTransformer
checkpoint and dump them to attn_real.npy  (shape: [n_heads, W, W]).

Run this ONCE in an environment that has torch installed:
    python extract_attention.py
Then re-run draw_bora_attention_v5.py -- it auto-detects attn_real.npy and
renders the real learned attention instead of the schematic patterns.

Model = TinyTransformer (2-layer encoder, d_model=32, nhead=4, FFN=64),
the 17,185-parameter reference detector. Checkpoint default: best_mm.pt.

Note: best_mm.pt is the univariate (1-channel, W=16) moment-matched detector,
so the maps are 16x16. That is the genuine trained attention; the figure's
64x64 5-channel depiction is the paper's reference schema.
"""
import os, numpy as np, torch, torch.nn as nn

D_MODEL, N_HEAD, FFN, N_LAYER = 32, 4, 64, 2
CKPT = os.environ.get("BORA_CKPT", "../pivot_v26/best_mm.pt")
W    = int(os.environ.get("BORA_W", "16"))     # window length the ckpt was trained on


class PositionalEncoding(nn.Module):
    def __init__(self, d, max_len=W):
        super().__init__()
        pe = torch.zeros(max_len, d); pos = torch.arange(max_len).unsqueeze(1).float()
        div = torch.exp(torch.arange(0, d, 2).float() * (-np.log(10000.0) / d))
        pe[:, 0::2] = torch.sin(pos * div); pe[:, 1::2] = torch.cos(pos * div)
        self.register_buffer("pe", pe)
    def forward(self, x): return x + self.pe[: x.size(1)]


class TinyTransformer(nn.Module):
    def __init__(self):
        super().__init__()
        self.proj = nn.Linear(1, D_MODEL)
        self.pe = PositionalEncoding(D_MODEL)
        layer = nn.TransformerEncoderLayer(D_MODEL, N_HEAD, FFN,
                                           batch_first=True, dropout=0.1)
        self.enc = nn.TransformerEncoder(layer, N_LAYER)
        self.head = nn.Linear(D_MODEL, 1)
    def embed(self, x):
        return self.pe(self.proj(x.unsqueeze(-1)))


def main():
    m = TinyTransformer()
    state = torch.load(CKPT, map_location="cpu")
    state = state.get("model", state) if isinstance(state, dict) else state
    m.load_state_dict(state, strict=False); m.eval()

    # a representative Byzantine-ish input window (replace with a real trace if
    # you have one of shape (W,)); the LEARNED WEIGHTS are what matter here.
    x = torch.linspace(0, 1, W).reshape(1, W)
    x[0, W//2:] += 0.6                       # a mid-window perturbation
    with torch.no_grad():
        h = m.embed(x)                       # (1, W, d_model)
        l0 = m.enc.layers[0].self_attn       # first-layer MHA
        Wi, bi = l0.in_proj_weight, l0.in_proj_bias
        q, k, _ = (h @ Wi.T + bi).chunk(3, dim=-1)        # (1,W,d_model) each
        dk = D_MODEL // N_HEAD
        q = q.reshape(1, W, N_HEAD, dk).permute(0, 2, 1, 3)   # (1,H,W,dk)
        k = k.reshape(1, W, N_HEAD, dk).permute(0, 2, 1, 3)
        att = torch.softmax((q @ k.transpose(-1, -2)) / dk**0.5, dim=-1)  # (1,H,W,W)
    A = att[0].numpy()                       # (H, W, W)
    np.save("attn_real.npy", A)
    print(f"saved attn_real.npy  shape={A.shape}  from {CKPT}")


if __name__ == "__main__":
    main()
