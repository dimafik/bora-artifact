"""BORA predictor daemon (ML in the loop).

*** SUPERSEDED -- DO NOT USE FOR NEW WORK. ***

Corrected 2026-09-03: an earlier version of this notice said this file was
not used for any reported measurement. That is wrong. No closed-loop cap
result came from it, but the in-loop detection trace of the paper's Fig. 6
and Section V-B did: `02_results_raw/mldetect_20260611-171955/
predictor_daemon.log` opens with `# daemon start thresh=0.65 fcap=2`, which
is this file's signature -- predictor_daemon_n.py prints `cap_rule=f-r-1`
instead. The defect below did not touch that measurement: one orderer was
degraded, so |B_t| never exceeded 1 and the static cap never bound.

This early version applies a static cap `[:FCAP]` with FCAP=2, which is wrong in
two ways against Algorithm 1 substep (c): it ignores the Raft-observed unhealthy
count r, and the constant itself admits |B_t| <= f rather than |B_t| < f. The
defect never showed up in practice because every campaign injected a single
degraded orderer, so |B_t| never exceeded 1.

The corrected daemon is `predictor_daemon_n.py` in this directory, which
implements `cap = max(0, F - r - 1)`. That is the one every closed-loop result in
the paper was produced with. This file is retained only so the correction is
auditable.

Reads the live in-network RTT feed, builds the trained 8-feature window per
orderer, runs the multi-head Transformer (best.pt), and emits B_t = {nodes whose
predicted leader-suitability Score < THRESH} (capped < f). Writes bt.json on the
shared path; a WSL pusher injects it as orderer advice. Logs every cycle for
detection-latency analysis. This replaces the operator-supplied B_t with a
telemetry-derived one."""
import sys, json, time, numpy as np, torch
sys.path.insert(0, "predictor")
from model import ScorePredictor, CONFIG

FEED = r"D:\fabric-d2\results\rtt_feed.csv"
BT   = r"D:\fabric-d2\results\bt.json"
LOG  = r"D:\fabric-d2\results\predictor_daemon.log"
K = CONFIG.window_len; ALPHA = 0.8
THRESH = float(sys.argv[1]) if len(sys.argv) > 1 else 0.65   # score below -> risky
FCAP = 2                                                     # |B_t| < f, f=2 -> <=1? keep <=FCAP
PERIOD = 0.5

m = ScorePredictor(CONFIG)
sd = torch.load("model_small/best.pt", map_location="cpu")
state = sd.get("model_state_dict", sd.get("state_dict", sd)) if isinstance(sd, dict) else sd
m.load_state_dict(state); m.eval()

def window(r):
    n = len(r); RTT = np.empty(n); RTT[0] = r[0]
    for t in range(1, n): RTT[t] = ALPHA*RTT[t-1] + (1-ALPHA)*r[t]
    Tc = np.full(n, 100.0); cc = (r <= Tc).astype(float)
    CC = np.convolve(cc, np.ones(min(20, n))/min(20, n), mode="same")
    dCC = np.diff(CC, prepend=CC[0]); dRTT = np.diff(RTT, prepend=RTT[0]); dz = np.zeros(n)
    return np.stack([cc, CC, r, RTT, Tc, dCC, dRTT, dz], axis=1).astype(np.float32)

def scores():
    try:
        rows = [l.strip().split(",") for l in open(FEED).read().splitlines() if l.strip()][-K:]
    except FileNotFoundError:
        return None
    if len(rows) < 10:
        return None
    out = {}
    for i in range(1, 6):
        r = np.array([float(x[i]) for x in rows], dtype=np.float64)
        X = window(r)
        with torch.no_grad():
            sc = float(m(torch.from_numpy(X).unsqueeze(0))["score"][0, 0, 1])
        out[i] = (sc, float(r[-5:].mean()))
    return out

seq = 5000
lg = open(LOG, "a", buffering=1)
lg.write(f"# daemon start thresh={THRESH} fcap={FCAP} ts={time.time():.3f}\n")
while True:
    s = scores()
    if s:
        risky = sorted([i for i in s if s[i][0] < THRESH], key=lambda i: s[i][0])[:FCAP]
        seq += 1
        json.dump({"blacklist": risky, "seq": seq, "fail_open": False,
                   "scores": {i: round(s[i][0], 3) for i in s}}, open(BT, "w"))
        lg.write(f"{time.time():.3f} Bt={risky} scores=" +
                 " ".join(f"o{i}:{s[i][0]:.2f}(rtt{s[i][1]:.0f})" for i in s) + "\n")
    time.sleep(PERIOD)
