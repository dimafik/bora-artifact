"""
model.py -- Score-Predictor for AI-Augmented S-Raft.

Light Transformer with 3 heads:
  A: Score regression (3 horizons × 3 quantiles)
  B: Anomaly detection (binary)
  C: Degradation prediction (binary, 1h horizon)

Designed for sub-millisecond inference on c5n.4xlarge CPU.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import torch
import torch.nn as nn


# =============================================================================
# Hyperparameters (locked at predictor pre-registration time)
# =============================================================================

@dataclass(frozen=True)
class PredictorConfig:
    window_len: int = 60          # K, ticks in input window
    n_features: int = 8           # cc, CC, rtt, RTT, T_commit, dCC, dRTT, design
    d_model: int = 64
    n_heads: int = 4
    d_ff: int = 128
    n_layers: int = 4
    dropout: float = 0.1
    horizons: tuple = (30, 60, 90)  # seconds into future for Score head
    quantiles: tuple = (0.1, 0.5, 0.9)


CONFIG = PredictorConfig()


# =============================================================================
# Positional encoding (sinusoidal)
# =============================================================================


class SinusoidalPE(nn.Module):
    def __init__(self, d_model: int, max_len: int = 256):
        super().__init__()
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len).unsqueeze(1).float()
        div_term = torch.exp(
            torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model)
        )
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer("pe", pe.unsqueeze(0))

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return x + self.pe[:, : x.size(1)]


# =============================================================================
# Score Predictor
# =============================================================================


class ScorePredictor(nn.Module):
    """
    Input  : (batch, K, d=8)  time-series window per node
    Outputs: dict with keys 'score', 'anomaly', 'degrade'
        score   : (batch, n_horizons, n_quantiles)
        anomaly : (batch, 1)  -- sigmoid output
        degrade : (batch, 1)  -- sigmoid output
    """

    def __init__(self, cfg: PredictorConfig = CONFIG):
        super().__init__()
        self.cfg = cfg

        self.input_proj = nn.Linear(cfg.n_features, cfg.d_model)
        self.pos_enc = SinusoidalPE(cfg.d_model, max_len=cfg.window_len + 4)

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=cfg.d_model,
            nhead=cfg.n_heads,
            dim_feedforward=cfg.d_ff,
            dropout=cfg.dropout,
            batch_first=True,
            activation="gelu",
        )
        self.encoder = nn.TransformerEncoder(encoder_layer, num_layers=cfg.n_layers)

        n_score_out = len(cfg.horizons) * len(cfg.quantiles)
        self.head_score = nn.Sequential(
            nn.Linear(cfg.d_model, 32), nn.ReLU(),
            nn.Linear(32, n_score_out),
        )
        self.head_anomaly = nn.Sequential(
            nn.Linear(cfg.d_model, 32), nn.ReLU(),
            nn.Linear(32, 1),
        )
        self.head_degrade = nn.Sequential(
            nn.Linear(cfg.d_model, 32), nn.ReLU(),
            nn.Linear(32, 1),
        )

    def forward(self, x: torch.Tensor) -> dict[str, torch.Tensor]:
        h = self.input_proj(x)
        h = self.pos_enc(h)
        h = self.encoder(h)
        z = h.mean(dim=1)

        score = self.head_score(z)
        score = score.view(-1, len(self.cfg.horizons), len(self.cfg.quantiles))
        score = torch.sigmoid(score)  # Score ∈ [0,1]

        anomaly = torch.sigmoid(self.head_anomaly(z))
        degrade = torch.sigmoid(self.head_degrade(z))

        return {"score": score, "anomaly": anomaly, "degrade": degrade}

    @torch.no_grad()
    def infer_advice(
        self,
        x: torch.Tensor,
        score_horizon_idx: int = 0,  # 0=30s, 1=60s, 2=90s
        anomaly_threshold: float = 0.5,
        degrade_threshold: float = 0.3,
        score_confidence_band: float = 0.1,
    ) -> dict:
        """
        Return a single Advice object per node row in x.

        Caller passes a batch where each row is a node's window. Caller is
        responsible for mapping batch index back to NodeId.

        Returns:
            {
              'sleep_ok'      : bool,  # whether advice should be trusted
              'score_pred'    : Tensor[B] median predicted Score
              'score_lo'      : Tensor[B] 10th percentile prediction
              'score_hi'      : Tensor[B] 90th percentile prediction
              'is_byzantine'  : Tensor[B] bool
              'is_degrading'  : Tensor[B] bool
            }
        """
        out = self.forward(x)
        score = out["score"][:, score_horizon_idx, :]  # (B, 3 quantiles)
        lo, med, hi = score[:, 0], score[:, 1], score[:, 2]

        # sleep_ok: confidence band width < threshold
        band = hi - lo
        sleep_ok_per_row = band < score_confidence_band
        sleep_ok_global = bool(sleep_ok_per_row.float().mean().item() >= 0.5)

        return {
            "sleep_ok":     sleep_ok_global,
            "score_pred":   med,
            "score_lo":     lo,
            "score_hi":     hi,
            "is_byzantine": out["anomaly"].squeeze(-1) > anomaly_threshold,
            "is_degrading": out["degrade"].squeeze(-1) > degrade_threshold,
            "anomaly_raw":  out["anomaly"].squeeze(-1),
            "degrade_raw":  out["degrade"].squeeze(-1),
        }


# =============================================================================
# Loss functions
# =============================================================================


def pinball_loss(y_pred: torch.Tensor, y_true: torch.Tensor, quantiles) -> torch.Tensor:
    """
    Quantile (pinball) loss.

    y_pred : (B, H, Q)
    y_true : (B, H)         -- actual Score at horizons
    quantiles: tuple of Q quantile levels in (0,1)
    """
    diffs = y_true.unsqueeze(-1) - y_pred           # (B, H, Q)
    q = torch.tensor(quantiles, device=y_pred.device).view(1, 1, -1)
    return torch.mean(torch.max(q * diffs, (q - 1) * diffs))


class MultiTaskLoss(nn.Module):
    """L = λ1 · pinball(score) + λ2 · BCE(anomaly) + λ3 · BCE(degrade)."""

    def __init__(self, w_score=1.0, w_anom=0.3, w_degr=0.3, quantiles=CONFIG.quantiles):
        super().__init__()
        self.w_score = w_score
        self.w_anom = w_anom
        self.w_degr = w_degr
        self.quantiles = quantiles
        self.bce = nn.BCELoss()

    def forward(self, pred, target) -> dict[str, torch.Tensor]:
        l_score = pinball_loss(pred["score"], target["score"], self.quantiles)
        l_anom = self.bce(pred["anomaly"].squeeze(-1), target["anomaly"].float())
        l_degr = self.bce(pred["degrade"].squeeze(-1), target["degrade"].float())
        total = self.w_score * l_score + self.w_anom * l_anom + self.w_degr * l_degr
        return {"loss": total, "l_score": l_score, "l_anom": l_anom, "l_degr": l_degr}


# =============================================================================
# Sanity check
# =============================================================================


if __name__ == "__main__":
    model = ScorePredictor()
    n_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"Model parameters: {n_params:,}")
    print(f"Estimated model size: {n_params * 4 / 1e6:.2f} MB (fp32)")

    # Synthetic batch
    B = 8
    x = torch.randn(B, CONFIG.window_len, CONFIG.n_features)
    out = model(x)
    print(f"score head : {out['score'].shape}")    # (B, 3, 3)
    print(f"anomaly    : {out['anomaly'].shape}")  # (B, 1)
    print(f"degrade    : {out['degrade'].shape}")  # (B, 1)

    advice = model.infer_advice(x)
    print(f"sleep_ok={advice['sleep_ok']}, "
          f"n_byz={int(advice['is_byzantine'].sum().item())}, "
          f"n_degr={int(advice['is_degrading'].sum().item())}")
