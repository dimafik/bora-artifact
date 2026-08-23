"""Closed-loop advisor: the blacklist comes from the detector, not the operator.

Why not predictor_daemon.py.  That daemon scores with model_small/best.pt and its
*score* head, over orderers 1-5.  The evasive sequences under test were optimised
against best_mm_r12.pt and its *anomaly* head, which is also the model whose
worst-case AUC the manuscript reports.  Pointing the loop at a different model
would answer a transfer question when the question asked is the white-box one.

Threshold, second attempt.  The first version calibrated on synthetic healthy
windows -- gen._white, mean 8 std 3, i.i.d. -- and then scored live RTT.  Live
telemetry is not that distribution: it carries container scheduling jitter, TLS
handshake costs and a floor near zero, so the synthetic quantile sat far too low
and the daemon blacklisted an unattacked orderer in almost every cycle, flagging
the target 18/40 times under the *healthy* track.  A detector whose false
positive rate is that high under no attack cannot be used to decide whether an
evasive attack was missed.

So the threshold is now measured on the live feed, during a calibration phase the
caller guarantees is attack-free.  Until it completes the daemon emits an empty
blacklist and writes no advice, and it records the phase boundary in the log so a
reader can tell calibration from measurement.
"""
import json
import os
import sys
import time

import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(HERE, "..", "predictor"))
import gen                                    # noqa: E402
from model import ScorePredictor, CONFIG      # noqa: E402

FEED = r"D:\fabric-d2\results\rtt_feed.csv"
BT = r"D:\fabric-d2\results\bt.json"
LOG = r"D:\fabric-d2\results\closed_loop_daemon.log"
READY = r"D:\fabric-d2\results\daemon_ready"
CKPT = os.path.join(HERE, "best_mm_r12.pt")

K = gen.K
N_ORD = 7
FCAP = 2                     # |B_t| < f - r ; f = 3 at N = 7
PERIOD = 0.5
FP_RATE = float(sys.argv[1]) if len(sys.argv) > 1 else 0.01
CALIB_SECS = float(sys.argv[2]) if len(sys.argv) > 2 else 90.0


def load_model():
    m = ScorePredictor(CONFIG)
    sd = torch.load(CKPT, map_location="cpu")
    if isinstance(sd, dict):
        sd = sd.get("model_state_dict", sd.get("state_dict", sd))
    m.load_state_dict(sd)
    m.eval()
    return m


def standardise(r):
    """Map a window to the training marginals: mean 8, std 3.

    The detector was trained where healthy and attack windows share those
    marginals and differ only in autocorrelation.  Live RTT does not share them
    -- orderer7 sits near 0.7 ms while the rest sit near 6-13 ms -- and scored
    raw, the head saturated: 0.9999 for roughly half the healthy nodes, flipping
    between cycles, with the attack-free mean at 0.99989.  Nothing can be
    thresholded out of that.

    This map is affine, so it leaves lag-1 autocorrelation exactly unchanged and
    removes only the level and scale the model was never meant to read.
    Measured over 280 live attack-free windows it takes the mean score from
    0.3187 to 0.0570 while synthetic AR(0.85-0.95) still scores 0.798.
    """
    r = np.asarray(r, dtype=np.float64)
    s = r.std()
    if s < 1e-9:
        return np.full_like(r, gen.MEAN)
    return (r - r.mean()) / s * gen.STD + gen.MEAN


def anomaly(m, r, raw=False):
    """r: (K,) RTT -> scalar anomaly score, the quantity PGD minimised."""
    x = np.asarray(r, dtype=np.float64) if raw else standardise(r)
    X = gen.window(x)
    with torch.no_grad():
        return float(m(torch.from_numpy(X).unsqueeze(0))["anomaly"].squeeze())


def read_feed():
    try:
        rows = [l.strip().split(",") for l in open(FEED).read().splitlines() if l.strip()]
    except OSError:
        return None
    rows = [r for r in rows if len(r) >= N_ORD + 1][-K:]
    if len(rows) < K:
        return None
    return {i: np.array([float(x[i]) for x in rows]) for i in range(1, N_ORD + 1)}


def write_bt(seq, risky, scores):
    json.dump({"blacklist": risky, "seq": seq, "fail_open": False,
               "scores": {i: round(scores[i], 4) for i in scores}},
              open(BT, "w"))


def main():
    for p in (READY,):
        if os.path.exists(p):
            os.remove(p)

    m = load_model()
    lg = open(LOG, "a", buffering=1)
    lg.write("# closed-loop start ckpt=%s fp_rate=%.3f calib=%.0fs fcap=%d ts=%.3f\n"
             % (os.path.basename(CKPT), FP_RATE, CALIB_SECS, FCAP, time.time()))

    # ---- calibration on live, attack-free telemetry -----------------------
    seq = 9000
    write_bt(seq, [], {})
    samples = []
    t_end = time.time() + CALIB_SECS
    print("calibrating on live feed for %.0fs ..." % CALIB_SECS, flush=True)
    while time.time() < t_end:
        feed = read_feed()
        if feed:
            samples.extend(anomaly(m, feed[i]) for i in feed)
        time.sleep(PERIOD)

    if len(samples) < 50:
        print("CALIBRATION_FAILED: only %d samples -- is the probe running?" % len(samples),
              flush=True)
        lg.write("# calibration failed, %d samples\n" % len(samples))
        return 1

    thr = float(np.quantile(samples, 1.0 - FP_RATE))
    lg.write("# calibrated thresh=%.6f from %d live samples "
             "(mean %.6f sd %.6f max %.6f) ts=%.3f\n"
             % (thr, len(samples), float(np.mean(samples)), float(np.std(samples)),
                float(np.max(samples)), time.time()))
    print("threshold %.6f from %d live samples (mean %.6f, max %.6f)"
          % (thr, len(samples), float(np.mean(samples)), float(np.max(samples))),
          flush=True)
    open(READY, "w").write("%.6f\n" % thr)

    # ---- measurement ------------------------------------------------------
    while True:
        feed = read_feed()
        if feed:
            sc = {i: anomaly(m, feed[i]) for i in feed}
            risky = [i for i, _ in sorted(sc.items(), key=lambda kv: -kv[1])
                     if sc[i] > thr][:FCAP]
            seq += 1
            write_bt(seq, risky, sc)
            lg.write("%.3f Bt=%s %s\n" % (time.time(), risky,
                     " ".join("o%d:%.4f(rtt%.1f)" % (i, sc[i], feed[i][-5:].mean())
                              for i in sorted(sc))))
        time.sleep(PERIOD)


if __name__ == "__main__":
    sys.exit(main())
