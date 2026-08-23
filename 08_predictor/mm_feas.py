"""Feasibility gate for path A: can the DEPLOYED best.pt separate a
moment-matched adversary (AR(1) autocorrelation, SAME marginal mean/var as
healthy white noise) using its anomaly/score heads? Pure offline test with the
deployed weights — if this fails, the live single-host loop will fail too."""
import sys, numpy as np, torch
sys.path.insert(0, "predictor")
from model import ScorePredictor, CONFIG
K = CONFIG.window_len; ALPHA = 0.8
rng = np.random.default_rng(0)

m = ScorePredictor(CONFIG)
sd = torch.load("model_small/best.pt", map_location="cpu")
state = sd.get("model_state_dict", sd.get("state_dict", sd)) if isinstance(sd, dict) else sd
m.load_state_dict(state); m.eval()

MEAN, STD, RHO = 8.0, 3.0, 0.9   # ms; healthy=white, attack=AR(1) same marginal

def white_rtt():
    return np.clip(rng.normal(MEAN, STD, K), 0.5, None)

def ar1_rtt():
    # AR(1) with stationary mean=MEAN, std=STD (match marginal moments)
    x = np.empty(K); x[0] = rng.normal(MEAN, STD)
    e = rng.normal(0, STD*np.sqrt(1-RHO**2), K)
    for t in range(1, K):
        x[t] = MEAN + RHO*(x[t-1]-MEAN) + e[t]
    return np.clip(x, 0.5, None)

def window(r):
    RTT = np.empty(K); RTT[0] = r[0]
    for t in range(1, K): RTT[t] = ALPHA*RTT[t-1]+(1-ALPHA)*r[t]
    Tc = np.full(K, 100.0); cc = (r <= Tc).astype(float)
    CC = np.convolve(cc, np.ones(20)/20, mode="same")
    dCC = np.diff(CC, prepend=CC[0]); dRTT = np.diff(RTT, prepend=RTT[0]); dz = np.zeros(K)
    return np.stack([cc, CC, r, RTT, Tc, dCC, dRTT, dz], axis=1).astype(np.float32)

def evalset(gen, n):
    sc, an = [], []
    for _ in range(n):
        X = torch.from_numpy(window(gen())).unsqueeze(0)
        with torch.no_grad(): o = m(X)
        sc.append(float(o["score"][0,0,1]))
        a = o["anomaly"][0,0]; an.append(float(torch.sigmoid(a)) if abs(float(a))>1 else float(a))
    return np.array(sc), np.array(an)

N=200
sc_h, an_h = evalset(white_rtt, N)   # healthy (label 0)
sc_a, an_a = evalset(ar1_rtt, N)     # moment-matched attack (label 1)

def auc(neg, pos):  # prob a random pos ranks above a random neg
    import itertools
    c=0; t=0
    for p in pos:
        c += np.sum(p>neg) + 0.5*np.sum(p==neg); t += len(neg)
    return c/t

print(f"marginal check: healthy rtt mean/std={np.mean([white_rtt().mean() for _ in range(50)]):.2f}/{np.mean([white_rtt().std() for _ in range(50)]):.2f}",
      f" attack={np.mean([ar1_rtt().mean() for _ in range(50)]):.2f}/{np.mean([ar1_rtt().std() for _ in range(50)]):.2f}")
print(f"SCORE   head: healthy {sc_h.mean():.3f}  attack {sc_a.mean():.3f}  AUC(low=attack)={auc(sc_a, sc_h):.3f}")
print(f"ANOMALY head: healthy {an_h.mean():.3f}  attack {an_a.mean():.3f}  AUC(high=attack)={auc(an_h, an_a):.3f}")
# threshold-on-mean-RTT baseline (should be ~0.5 since marginals match)
mh=[white_rtt().mean() for _ in range(N)]; ma=[ar1_rtt().mean() for _ in range(N)]
print(f"threshold(meanRTT) baseline AUC={auc(np.array(mh), np.array(ma)):.3f}  (expect ~0.5)")
