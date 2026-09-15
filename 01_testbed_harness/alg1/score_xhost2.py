# -*- coding: utf-8 -*-
"""Score a cross-host feed with the deployed predictor, offline.  Decision
rules are fixed here before any result is read.

  onset   the first tick at which a 10-tick rolling median of the target
          exceeds 10x its own clean median -- a one- or two-tick transient
          cannot move a 10-tick median, and the AWS path produces those.
  theta   two values are reported side by side:
            fitted     = min over clean-phase windows of the four healthy
                         orderers, i.e. below anything seen on clean traffic
                         from this cluster.  This is the calibration Sec. V-G
                         prescribes.
            transplant = 0.65, the single-host value, carried over unchanged.
                         Sec. V-G says not to do this; here is what happens.
  detect  first attack-phase tick at which the target scores below theta,
          matching the daemon, which blacklists on one cycle (no streak).
  FP      healthy-orderer windows below theta in the ATTACK phase only --
          held out of calibration, so this is a measurement and not an
          artefact of how theta was set.

Every combination of Tc in {100 (deployed), 5 (re-fitted)} and
standardisation in {off, on} is run.  Which one works is part of the result.
"""
import sys, os, json
import numpy as np, torch

HERE = os.path.dirname(os.path.abspath(__file__))
PRED = os.environ.get("PREDICTOR_DIR", os.path.join(HERE, "..", "..", "08_predictor"))
sys.path.insert(0, os.path.join(PRED, "predictor"))
sys.path.insert(0, PRED)
from model import ScorePredictor, CONFIG

K       = CONFIG.window_len      # 60
ALPHA   = 0.8
UNRESP  = 1000.0                 # probe.py's connect-failure sentinel
N_ORD   = 5
TARGET  = 3                      # orderer3 is the attacked node
MEDW    = 10                     # rolling median width for onset
THETA_TRANSPLANT = 0.65          # the single-host value of Sec. V-B


def load_model(path=None):
    path = path or os.path.join(PRED, "model_small", "best.pt")
    m = ScorePredictor(CONFIG)
    sd = torch.load(path, map_location="cpu", weights_only=False)
    if isinstance(sd, dict):
        for k in ("model_state_dict", "state_dict", "model"):
            if k in sd and isinstance(sd[k], dict):
                sd = sd[k]; break
    m.load_state_dict(sd); m.eval()
    return m


def standardise(r, mean=8.0, std=3.0):
    r = np.asarray(r, dtype=np.float64)
    s = r.std()
    if s < 1e-9:
        return np.full_like(r, mean)
    return (r - r.mean()) / s * std + mean


def window(r, Tc_ms):
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
    with torch.no_grad():
        return float(m(torch.from_numpy(window(x, Tc_ms)).unsqueeze(0))["score"][0, 0, 1])


def read_feed(path):
    rows = []
    for line in open(path):
        p = line.strip().split(",")
        if len(p) >= N_ORD + 1:
            try: rows.append([float(x) for x in p[:N_ORD + 1]])
            except ValueError: pass
    t = np.array([r[0] for r in rows])
    R = {i: np.array([r[i] for r in rows]) for i in range(1, N_ORD + 1)}
    return t, R


def onset_tick(R, target=TARGET, factor=10.0, floor_ms=5.0, w=MEDW):
    """First tick whose trailing w-tick median exceeds factor x the clean median."""
    v = R[target]
    base = float(np.median(v[:K]))
    thr = max(factor * base, floor_ms)
    for k in range(K, len(v) - w):
        if np.median(v[k:k + w]) > thr:
            return k, base, thr
    return None, base, thr


def transients(R, onset, mult=5.0, floor_ms=3.0):
    """Healthy-orderer ticks that spike well above their own clean median.
    Reported, not removed: they are what the AWS path actually does."""
    out = {}
    for i in R:
        if i == TARGET: continue
        v = R[i]
        b = float(np.median(v[:K]))
        thr = max(mult * b, floor_ms)
        sp = [int(k) for k in np.where(v > thr)[0]]
        if sp:
            out["orderer%d" % i] = {"ticks": sp[:12], "n": len(sp),
                                    "max_ms": round(float(v.max()), 2),
                                    "clean_median_ms": round(b, 3)}
    return out


def analyse(feed, Tc_ms, std_first, model):
    t, R = read_feed(feed)
    on, base, thr = onset_tick(R)
    tag = {"feed": os.path.basename(os.path.dirname(feed)),
           "Tc_ms": Tc_ms, "standardised": bool(std_first)}
    if on is None:
        return dict(tag, error="no sustained attack phase -- discard this feed")

    n = len(t)
    S = {i: np.full(n - K, np.nan) for i in R}
    for k in range(K, n):
        for i in R:
            seg = R[i][k - K:k]
            seg = seg[seg < UNRESP]
            if len(seg) >= 10:
                S[i][k - K] = score_window(model, seg, Tc_ms, std_first)

    # window index w corresponds to tick w+K
    clean_w  = [w for w in range(len(S[TARGET])) if w + K < on]
    attack_w = [w for w in range(len(S[TARGET])) if w + K >= on]
    calib = np.concatenate([S[i][clean_w] for i in S if i != TARGET]) if clean_w else np.array([])
    calib = calib[~np.isnan(calib)]
    if len(calib) < 100:
        return dict(tag, error="calibration set too small (%d)" % len(calib))

    res = dict(tag,
               n_ticks=n, onset_tick=on,
               clean_median_ms=round(base, 3),
               attack_median_ms=round(float(np.median(R[TARGET][on:])), 3),
               calib_windows=int(len(calib)),
               attack_windows=len(attack_w),
               target_score_clean=round(float(np.nanmedian(S[TARGET][clean_w])), 4),
               target_score_attack=round(float(np.nanmedian(S[TARGET][attack_w])), 4),
               calib_min=round(float(calib.min()), 4),
               calib_p50=round(float(np.median(calib)), 4))

    for name, theta in (("fitted", float(calib.min())),
                        ("transplant", THETA_TRANSPLANT)):
        tv = S[TARGET]
        det = next((w for w in attack_w if tv[w] < theta), None)
        lat = float(t[det + K] - t[on]) if det is not None else None
        held = int(np.nansum(tv[attack_w] < theta))
        fp_per = {("orderer%d" % i): int(np.nansum(S[i][attack_w] < theta))
                  for i in S if i != TARGET}
        res[name] = {"theta": round(theta, 4),
                     "detection_latency_s": (round(lat, 2) if lat is not None else None),
                     "held_cycles": held, "attack_cycles": len(attack_w),
                     "held_frac": round(held / len(attack_w), 3) if attack_w else None,
                     "false_positives": fp_per,
                     "fp_total": sum(fp_per.values()),
                     "fp_windows": 4 * len(attack_w),
                     "fp_rate": round(sum(fp_per.values()) / (4.0 * len(attack_w)), 4)}
    res["healthy_transients"] = transients(R, on)
    return res


if __name__ == "__main__":
    feeds = sys.argv[1:]
    m = load_model()
    print("model params: %d" % sum(p.numel() for p in m.parameters()), file=sys.stderr)
    out = []
    for f in feeds:
        for Tc in (100.0, 5.0):
            for std in (False, True):
                r = analyse(f, Tc, std, m)
                out.append(r)
                if "error" in r:
                    print("  %-6s Tc=%-5s std=%-5s -> %s" % (r["feed"], Tc, std, r["error"]),
                          file=sys.stderr)
                else:
                    for nm in ("fitted", "transplant"):
                        d = r[nm]
                        print("  %-6s Tc=%-5s std=%-5s %-10s th=%.4f lat=%-6s held=%d/%d fp=%d/%d"
                              % (r["feed"], Tc, std, nm, d["theta"],
                                 d["detection_latency_s"], d["held_cycles"],
                                 d["attack_cycles"], d["fp_total"], d["fp_windows"]),
                              file=sys.stderr)
    print(json.dumps(out, indent=1, ensure_ascii=False))
