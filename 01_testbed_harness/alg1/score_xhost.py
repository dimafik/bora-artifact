# -*- coding: utf-8 -*-
"""Score a cross-host feed with the deployed predictor, offline.

Produces on cross-host telemetry the same three numbers Fig. 4 gives on one
host: detection latency, fraction of attack cycles the target is held, and
false positives among the healthy orderers.

Four combinations are run. Which one is needed is part of the result.
  raw / Tc=100  : the deployed pipeline unchanged
  raw / Tc=re-fitted
  std / Tc=100  : with closed_loop_daemon's per-window standardisation
  std / Tc=re-fitted
"""
import sys, os, json
import numpy as np, torch

HERE = os.path.dirname(os.path.abspath(__file__))
PRED = os.environ.get("PREDICTOR_DIR", os.path.join(HERE, "..", "..", "08_predictor"))
sys.path.insert(0, os.path.join(PRED, "predictor"))
sys.path.insert(0, PRED)
from model import ScorePredictor, CONFIG

K      = CONFIG.window_len      # 60
ALPHA  = 0.8
UNRESP = 1000.0                 # probe.py's connect-failure sentinel
N_ORD  = 5
TARGET = 3                      # orderer3 is the attacked node


def load_model(path=None):
    path = path or os.path.join(PRED, "model_small", "best.pt")
    m = ScorePredictor(CONFIG)
    sd = torch.load(path, map_location="cpu", weights_only=False)
    if isinstance(sd, dict):
        for k in ("model_state_dict", "state_dict", "model"):
            if k in sd and isinstance(sd[k], dict):
                sd = sd[k]
                break
    m.load_state_dict(sd)
    m.eval()
    return m


def standardise(r, mean=8.0, std=3.0):
    """closed_loop_daemon.standardise: map a window to the training marginals.
    Affine, so it leaves lag-1 autocorrelation exactly unchanged."""
    r = np.asarray(r, dtype=np.float64)
    s = r.std()
    if s < 1e-9:
        return np.full_like(r, mean)
    return (r - r.mean()) / s * std + mean


def window(r, Tc_ms):
    """predictor_daemon_n.window, with Tc as an argument instead of a constant."""
    r = np.asarray(r, dtype=np.float64)
    n = len(r)
    RTT = np.empty(n); RTT[0] = r[0]
    for t in range(1, n):
        RTT[t] = ALPHA * RTT[t-1] + (1 - ALPHA) * r[t]
    Tc  = np.full(n, float(Tc_ms))
    cc  = (r <= Tc).astype(float)
    w   = min(20, n)
    CC  = np.convolve(cc, np.ones(w) / w, mode="same")
    dCC = np.diff(CC,  prepend=CC[0])
    dRTT = np.diff(RTT, prepend=RTT[0])
    dz  = np.zeros(n)
    return np.stack([cc, CC, r, RTT, Tc, dCC, dRTT, dz], axis=1).astype(np.float32)


def score_window(m, r, Tc_ms, std_first):
    x = standardise(r) if std_first else np.asarray(r, dtype=np.float64)
    X = window(x, Tc_ms)
    with torch.no_grad():
        return float(m(torch.from_numpy(X).unsqueeze(0))["score"][0, 0, 1])


def read_feed(path):
    rows = []
    for line in open(path):
        p = line.strip().split(",")
        if len(p) >= N_ORD + 1:
            try:
                rows.append([float(x) for x in p[:N_ORD + 1]])
            except ValueError:
                pass
    t = np.array([r[0] for r in rows])
    R = {i: np.array([r[i] for r in rows]) for i in range(1, N_ORD + 1)}
    return t, R


def onset_tick(R, target=TARGET, factor=10.0, floor_ms=5.0):
    """First tick at which the target exceeds factor x its own baseline median.

    The search starts at tick K: a window before that is not fully inside the
    clean phase anyway, and the probe's very first connects can spike while the
    cluster settles (seed 1 opened with a 7.5 ms tick)."""
    v = R[target]
    base = float(np.median(v[:K]))
    thr = max(factor * base, floor_ms)
    idx = np.where(v[K:] > thr)[0]
    return (int(idx[0]) + K if len(idx) else None), base, thr


def run(feed, Tc_ms, std_first, quantile=0.02, model=None):
    m = model if model is not None else load_model()
    t, R = read_feed(feed)
    on, base, thr = onset_tick(R)
    tag = {"feed": os.path.basename(os.path.dirname(feed)),
           "Tc_ms": Tc_ms, "standardised": bool(std_first)}
    if on is None:
        return dict(tag, error="no attack phase -- discard this feed")

    n = len(t)
    unresp = {i: int((R[i] >= UNRESP).sum()) for i in R}

    S = {i: [] for i in R}
    for k in range(K, n):
        for i in R:
            seg = R[i][k - K:k]
            seg = seg[seg < UNRESP]
            S[i].append(score_window(m, seg, Tc_ms, std_first)
                        if len(seg) >= 10 else np.nan)
    S = {i: np.asarray(S[i], dtype=float) for i in S}

    # theta is calibrated on the healthy orderers *before* onset (Sec. V-G)
    base_idx = [k for k in range(len(S[TARGET])) if k + K < on]
    healthy = np.concatenate([S[i][base_idx] for i in S if i != TARGET]) \
              if base_idx else np.array([])
    healthy = healthy[~np.isnan(healthy)]
    if len(healthy) < 20:
        return dict(tag, error="calibration phase too short (%d)" % len(healthy))
    theta = float(np.quantile(healthy, quantile))

    tv = S[TARGET]
    det = None
    for k in range(len(tv) - 1):
        if k + K >= on and tv[k] < theta and tv[k + 1] < theta:
            det = k + 1 + K
            break
    lat = float(t[det] - t[on]) if det is not None else None

    held = int(sum(1 for k in range(len(tv)) if k + K >= on and tv[k] < theta))
    atk = int(sum(1 for k in range(len(tv)) if k + K >= on))
    fp = {("orderer%d" % i): int(np.nansum(S[i] < theta))
          for i in S if i != TARGET}

    return dict(tag,
                base_median_ms=round(base, 3),
                onset_tick=on,
                attack_median_ms=round(float(np.median(R[TARGET][on:])), 3),
                theta=round(theta, 4),
                target_score_base=round(float(np.nanmedian(tv[base_idx])), 4) if base_idx else None,
                target_score_attack=round(float(np.nanmedian(
                    [tv[k] for k in range(len(tv)) if k + K >= on])), 4),
                detection_latency_s=(round(lat, 2) if lat is not None else None),
                held_cycles=held, attack_cycles=atk,
                held_frac=(round(held / atk, 3) if atk else None),
                false_positives=fp,
                unresponsive_samples=unresp)


if __name__ == "__main__":
    feeds = sys.argv[1:]
    m = load_model()
    print("model params: %d" % sum(p.numel() for p in m.parameters()),
          file=sys.stderr)
    out = []
    for f in feeds:
        for Tc in (100.0, 5.0):
            for std in (False, True):
                r = run(f, Tc, std, model=m)
                out.append(r)
                print("  %-6s Tc=%-5s std=%-5s -> %s"
                      % (r["feed"], r["Tc_ms"], r["standardised"],
                         r.get("error") or ("lat=%ss held=%s/%s fp=%s"
                                            % (r["detection_latency_s"],
                                               r["held_cycles"], r["attack_cycles"],
                                               sum(r["false_positives"].values())))),
                      file=sys.stderr)
    print(json.dumps(out, indent=1, ensure_ascii=False))
