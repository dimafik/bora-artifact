"""RelationalScorePredictor: the deployed encoder plus the operator it lacks.

WHY.  BORA's decision has five properties, and each of them is a requirement on
the operator, not a preference:

  1. the output B_t is a SET of node ids  -> permutation equivariance, and the
     per-node identity must survive to the output
  2. N changes while the system runs (5..21, joint consensus, Section III-H)
     -> the operator must accept a variable number of inputs
  3. the judgement is comparative -- "is this orderer worse than its peers"
     -> pairwise comparison
  4. under a moment-matched adversary the absolute level carries no information
     -> only the cross-node structure is left to decide on
  5. orderers have no natural ordering -> no adjacency may be assumed
     (this is why a convolution over the node axis fails outright, 0.51)

Attention over the node axis satisfies all five by construction.  The deployed
ScorePredictor puts its attention over TIME within one node and scores nodes
independently (see infer_advice: "each row is a node's window"), which satisfies
none of them.  Four rounds of experiments found no advantage for the temporal
attention; the multi-node experiments found a consistent one for the node-axis
attention it does not have.

WHERE THE LAYER GOES.  Before temporal pooling.  Placing it after was the fault
found three times in this analysis: a time-averaged per-node embedding no longer
carries the waveform a comparison needs (D1 attention 0.248 -> 0.671 once moved).

The per-node output is preserved, so infer_advice and Algorithm 1 are unchanged.
"""
import sys
import torch
import torch.nn as nn

sys.path.insert(0, ".."); sys.path.insert(0, "../predictor")
from model import ScorePredictor, CONFIG


class RelationalScorePredictor(nn.Module):
    """(B, N, K, 8) -> per-node anomaly logit (B, N).

    relational=False reproduces the deployed model exactly: every node is encoded
    and scored on its own.  That is the control, not a straw man.
    """

    def __init__(self, cfg=CONFIG, relational="attention", n_heads=4):
        """relational: "none" reproduces the deployed model (per-node, independent);
        "deepsets" is the canonical permutation-invariant operator -- each node
        sees the mean of all nodes, no pairwise term; "attention" is pairwise.

        DeepSets is here because without it "attention is needed" is not a claim
        anyone has to accept: the obvious question is whether simply broadcasting
        the cross-node mean would do, and that has to be measured, not assumed."""
        super().__init__()
        if relational is True:
            relational = "attention"
        if relational is False:
            relational = "none"
        self.cfg, self.relational = cfg, relational
        self.base = ScorePredictor(cfg)
        d = cfg.d_model
        if relational == "attention":
            self.node_attn = nn.MultiheadAttention(d, n_heads, batch_first=True)
            self.node_norm = nn.LayerNorm(d)
        elif relational == "deepsets":
            self.ds = nn.Sequential(nn.Linear(2 * d, d), nn.ReLU(), nn.Linear(d, d))
            self.node_norm = nn.LayerNorm(d)
        self.pool_q = nn.Parameter(torch.randn(d) * 0.02)
        self.head = nn.Sequential(nn.Linear(d, 32), nn.ReLU(), nn.Linear(32, 1))

    def forward(self, X):
        B, N, K, _ = X.shape
        d = self.cfg.d_model
        h = self.base.input_proj(X.reshape(B * N, K, -1))          # B*N, K, d

        # N = 1 has nothing to relate.  Without this guard the layer still runs:
        # softmax over a single element is 1.0, so attention returns the input,
        # and the residual + LayerNorm then rescales the representation the
        # temporal encoder sees.  Measured cost of leaving it in: the single-node
        # detection task falls from 1.000 to 0.502 -- the layer is pure loss
        # there.  Skipping it makes the single-node path identical to the
        # deployed model by construction, so no regression is possible.
        if self.relational != "none" and N > 1:
            # compare nodes at every tick, before any pooling
            hn = h.reshape(B, N, K, d).permute(0, 2, 1, 3).reshape(B * K, N, d)
            if self.relational == "attention":
                a, _ = self.node_attn(hn, hn, hn)
            else:                                  # deepsets
                m = hn.mean(1, keepdim=True).expand_as(hn)
                a = self.ds(torch.cat([hn, m], dim=-1))
            hn = self.node_norm(hn + a)
            h = hn.reshape(B, K, N, d).permute(0, 2, 1, 3).reshape(B * N, K, d)

        h = self.base.encoder(self.base.pos_enc(h))                # temporal
        w = torch.softmax((h @ self.pool_q) / d ** 0.5, dim=1)
        z = (h * w.unsqueeze(-1)).sum(1)                           # B*N, d
        return self.head(z).reshape(B, N)                          # per-node


def count(m):
    return sum(p.numel() for p in m.parameters())


if __name__ == "__main__":
    for rel in ("none", "deepsets", "attention"):
        m = RelationalScorePredictor(relational=rel)
        for N in (5, 7, 21):
            x = torch.randn(3, N, CONFIG.window_len, 8)
            with torch.no_grad():
                o = m(x)
            assert o.shape == (3, N), o.shape
        print("relational=%-10s params=%d  variable-N ok" % (rel, count(m)))
