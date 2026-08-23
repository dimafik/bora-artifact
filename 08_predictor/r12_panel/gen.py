"""Shared data generator for the R12 detector panel.

Identical task, representation and marginals to mm_train.py -- healthy windows are
white-noise RTT, attack windows are AR(1) RTT with the SAME mean and variance, so
only the autocorrelation differs.  Kept in one place so every model in the panel
sees exactly the same data and the comparison means something.

The only change from mm_train.py is scale: it trained a 141k-parameter model on
800 windows, which is 176 parameters per sample.  The data is synthetic, so more
of it costs nothing.
"""
import numpy as np
import torch

K = 60            # CONFIG.window_len
MEAN, STD = 8.0, 3.0
ALPHA = 0.8


def _white(rng):
    return np.clip(rng.normal(MEAN, STD, K), 0.5, None)


def _ar1(rng, rho):
    x = np.empty(K)
    x[0] = rng.normal(MEAN, STD)
    e = rng.normal(0, STD * np.sqrt(1 - rho ** 2), K)
    for t in range(1, K):
        x[t] = MEAN + rho * (x[t - 1] - MEAN) + e[t]
    return np.clip(x, 0.5, None)


def window(r):
    """Eight-channel window exactly as the deployed daemon builds it."""
    RTT = np.empty(K)
    RTT[0] = r[0]
    for t in range(1, K):
        RTT[t] = ALPHA * RTT[t - 1] + (1 - ALPHA) * r[t]
    Tc = np.full(K, 100.0)
    cc = (r <= Tc).astype(float)
    CC = np.convolve(cc, np.ones(20) / 20, mode="same")
    dCC = np.diff(CC, prepend=CC[0])
    dRTT = np.diff(RTT, prepend=RTT[0])
    dz = np.zeros(K)
    return np.stack([cc, CC, r, RTT, Tc, dCC, dRTT, dz], axis=1).astype(np.float32)


def make(n, seed):
    """n healthy + n attack windows.  Returns (X, y, raw) with raw RTT kept so the
    white-box attack can perturb the same quantity the adversary controls."""
    rng = np.random.default_rng(seed)
    X, y, raw = [], [], []
    for _ in range(n):
        r = _white(rng)
        X.append(window(r)); y.append(0); raw.append(r)
        r = _ar1(rng, rng.uniform(0.85, 0.95))
        X.append(window(r)); y.append(1); raw.append(r)
    return (torch.tensor(np.stack(X)),
            torch.tensor(y, dtype=torch.float32),
            np.stack(raw).astype(np.float32))


def window_torch(r):
    """Differentiable version of window() for PGD.  r: (B, K) tensor.

    Cast to float32 on entry: numpy generates float64 by default and the fixed
    convolution kernel below is float32, which otherwise raises mid-graph."""
    r = r.float()
    B = r.shape[0]
    RTT = [r[:, 0]]
    for t in range(1, K):
        RTT.append(ALPHA * RTT[-1] + (1 - ALPHA) * r[:, t])
    RTT = torch.stack(RTT, dim=1)
    Tc = torch.full_like(r, 100.0)
    cc = torch.sigmoid((Tc - r) * 50.0)            # smooth (r <= Tc)
    kern = torch.ones(1, 1, 20, device=r.device) / 20.0
    CC = torch.nn.functional.conv1d(cc.unsqueeze(1), kern, padding=10)[:, 0, :K]
    dCC = torch.cat([torch.zeros(B, 1, device=r.device), CC[:, 1:] - CC[:, :-1]], 1)
    dRTT = torch.cat([torch.zeros(B, 1, device=r.device), RTT[:, 1:] - RTT[:, :-1]], 1)
    dz = torch.zeros_like(r)
    return torch.stack([cc, CC, r, RTT, Tc, dCC, dRTT, dz], dim=2)


def summarise(X):
    """40 summary statistics per window: mean/std/min/max/lag1-autocorr per channel."""
    x = X.numpy() if torch.is_tensor(X) else X
    out = []
    for c in range(x.shape[2]):
        ch = x[:, :, c]
        m = ch.mean(1); s = ch.std(1) + 1e-9
        z = (ch - m[:, None]) / s[:, None]
        ac = (z[:, :-1] * z[:, 1:]).mean(1)
        out += [m, s, ch.min(1), ch.max(1), ac] if False else [m, s, ch.min(axis=1), ch.max(axis=1), ac]
    return np.stack(out, axis=1)


def auc(y, s):
    y = np.asarray(y); s = np.asarray(s)
    pos, neg = s[y == 1], s[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    c = sum(np.sum(p > neg) + 0.5 * np.sum(p == neg) for p in pos)
    return float(c / (len(pos) * len(neg)))
