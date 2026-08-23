"""Gate: read the in-network RTT feed, build the trained 8-feature window, run
best.pt, print per-orderer meanRTT / predicted Score / anomaly. If the attacked
orderer (o3) is clearly separated, the live ML-in-loop is feasible."""
import sys, numpy as np, torch
sys.path.insert(0, "predictor")
from model import ScorePredictor, CONFIG
FEED = r"D:\fabric-d2\results\rtt_feed.csv"
K = CONFIG.window_len; ALPHA = 0.8

rows = [l.strip().split(",") for l in open(FEED).read().splitlines() if l.strip()]
rows = rows[-K:]
print(f"rows={len(rows)}")
rtt = {i: np.array([float(r[i]) for r in rows], dtype=np.float64) for i in range(1, 6)}

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

print(f"{'node':>4} {'meanRTT':>8} {'score30':>8} {'anomaly':>8}")
for i in range(1, 6):
    X = window(rtt[i])
    with torch.no_grad(): out = m(torch.from_numpy(X).unsqueeze(0))
    sc = float(out["score"][0, 0, 1])
    a = out["anomaly"][0, 0]; a = float(torch.sigmoid(a)) if abs(float(a)) > 1 else float(a)
    print(f"o{i:>3} {rtt[i].mean():8.1f} {sc:8.3f} {a:8.3f}")
