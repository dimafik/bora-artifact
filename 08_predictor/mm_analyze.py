"""In-loop AUC for the live moment-matched experiment. Reads rtt_feed.csv
(ts,o1..o5) + mm_t0.txt (attack onset). Builds sliding K-windows per node,
runs best_mm.pt's anomaly head, and labels: positive = o3 windows fully inside
the attack phase; negative = any window fully inside baseline + non-o3 windows.
Reports Transformer AUC vs threshold(mean RTT) and threshold(std RTT)."""
import sys, numpy as np, torch
sys.path.insert(0, "predictor")
from model import ScorePredictor, CONFIG
K = CONFIG.window_len; ALPHA = 0.8
FEED = r"D:\fabric-d2\results\rtt_feed.csv"
T0 = float(open(r"D:\fabric-d2\results\mm_t0.txt").read().strip())

rows = [l.strip().split(",") for l in open(FEED).read().splitlines() if l.strip()]
ts = np.array([float(r[0]) for r in rows])
rtt = {n: np.array([float(r[n]) for r in rows]) for n in range(1, 6)}

m = ScorePredictor(CONFIG)
m.load_state_dict(torch.load("best_mm.pt", map_location="cpu")); m.eval()

def window(r):
    RTT = np.empty(K); RTT[0]=r[0]
    for t in range(1,K): RTT[t]=ALPHA*RTT[t-1]+(1-ALPHA)*r[t]
    Tc=np.full(K,100.0); cc=(r<=Tc).astype(float)
    CC=np.convolve(cc,np.ones(20)/20,mode="same")
    dCC=np.diff(CC,prepend=CC[0]); dRTT=np.diff(RTT,prepend=RTT[0]); dz=np.zeros(K)
    return np.stack([cc,CC,r,RTT,Tc,dCC,dRTT,dz],axis=1).astype(np.float32)

anom_pos, anom_neg, mean_pos, mean_neg, std_pos, std_neg = [],[],[],[],[],[]
N = len(ts)
for n in range(1, 6):
    for i in range(0, N-K, 3):
        w_ts = ts[i:i+K]
        r = rtt[n][i:i+K]
        with torch.no_grad():
            a = m(torch.from_numpy(window(r)).unsqueeze(0))["anomaly"][0,0]
            a = float(torch.sigmoid(a)) if abs(float(a))>1 else float(a)
        mu, sg = r.mean(), r.std()
        if n == 3 and w_ts[0] >= T0:           # o3 fully in attack -> positive
            anom_pos.append(a); mean_pos.append(mu); std_pos.append(sg)
        elif w_ts[-1] < T0 or n != 3:          # baseline (any node) or non-o3 -> negative
            anom_neg.append(a); mean_neg.append(mu); std_neg.append(sg)

def auc(neg, pos):
    neg=np.array(neg); pos=np.array(pos)
    return sum(np.sum(p>neg)+0.5*np.sum(p==neg) for p in pos)/(len(pos)*len(neg))

print(f"windows: pos(o3 attack)={len(anom_pos)} neg(healthy)={len(anom_neg)}")
print(f"Transformer anomaly  AUC = {auc(anom_neg, anom_pos):.3f}")
print(f"threshold mean-RTT   AUC = {auc(mean_neg, mean_pos):.3f}  (expect ~0.5: marginals matched)")
print(f"threshold std-RTT    AUC = {auc(std_neg, std_pos):.3f}")
print(f"o3-attack anomaly mean={np.mean(anom_pos):.3f}  healthy anomaly mean={np.mean(anom_neg):.3f}")
print(f"o3-attack meanRTT={np.mean(mean_pos):.2f}  healthy meanRTT={np.mean(mean_neg):.2f}")
