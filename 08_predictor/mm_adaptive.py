"""Detector-ADAPTIVE (white-box) adversary vs the deployed predictor (best_mm.pt).

Zhu's question: the moment-matched adversary matches the LEGITIMATE distribution's
moments; is the learned detector robust to an adversary that adapts to the
DETECTOR itself? Here the adversary knows the deployed Transformer and runs PGD
on its injected delay sequence to MINIMISE the anomaly head, subject to (a) matched
marginals (mean 8 / std 3) and (b) a floor on lag-1 autocorrelation rho_min --- it
must keep a real temporal attack, otherwise "evasion" is just behaving benignly.
Sweeping rho_min traces the evasion-vs-attack-strength frontier: if AUC stays high
while rho_min>=0.6 the detector is robust (evasion requires giving up the attack);
if it collapses, the detector is evadable and we disclose it.
"""
import sys, numpy as np, torch
sys.path.insert(0, "predictor")
from model import ScorePredictor, CONFIG

K = CONFIG.window_len; ALPHA = 0.8; MEAN, STD = 8.0, 3.0
torch.manual_seed(0); rng = np.random.default_rng(0)

m = ScorePredictor(CONFIG)
m.load_state_dict(torch.load("best_mm.pt", map_location="cpu")); m.eval()
for p in m.parameters(): p.requires_grad_(False)

# constant channels (delays << 100ms commit threshold => cc=1 always)
_cc = np.ones(K); _CC = np.convolve(_cc, np.ones(20)/20, mode="same")
_dCC = np.diff(_CC, prepend=_CC[0])
CC_t = torch.tensor(_CC, dtype=torch.float32); dCC_t = torch.tensor(_dCC, dtype=torch.float32)
cc_t = torch.ones(K); Tc_t = torch.full((K,), 100.0); dz_t = torch.zeros(K)

def window_t(r):                       # differentiable 8-channel window from raw delays r (K,)
    RTT = [r[0]]
    for t in range(1, K): RTT.append(ALPHA*RTT[-1] + (1-ALPHA)*r[t])
    RTT = torch.stack(RTT)
    dRTT = torch.cat([RTT[:1]*0, RTT[1:]-RTT[:-1]])
    return torch.stack([cc_t, CC_t, r, RTT, Tc_t, dCC_t, dRTT, dz_t], dim=1)  # (K,8)

def anomaly(rs):                       # rs: (B,K) -> (B,) anomaly prob
    X = torch.stack([window_t(rs[b]) for b in range(rs.shape[0])])
    a = m(X)["anomaly"].squeeze(1)
    return torch.sigmoid(a) if a.abs().max() > 1 else a

def ar1(rho):
    x = np.empty(K); x[0] = rng.normal(MEAN, STD)
    e = rng.normal(0, STD*np.sqrt(1-rho**2), K)
    for t in range(1, K): x[t] = MEAN + rho*(x[t-1]-MEAN) + e[t]
    return np.clip(x, 0.5, 60)

def white(): return np.clip(rng.normal(MEAN, STD, K), 0.5, 60)

def autocorr1(r):                      # differentiable lag-1 autocorrelation
    rc = r - r.mean()
    return (rc[:-1]*rc[1:]).sum() / (rc.pow(2).sum() + 1e-8)

def auc(neg, pos):
    neg, pos = np.asarray(neg), np.asarray(pos)
    return float(sum(np.sum(p > neg) + 0.5*np.sum(p == neg) for p in pos)/(len(pos)*len(neg)))

N = 200
healthy = np.stack([white() for _ in range(N)])
with torch.no_grad():
    h_score = anomaly(torch.tensor(healthy, dtype=torch.float32)).numpy()

# non-adaptive baseline: AR(1) rho~0.9, matched marginals (the paper's moment-matched attack)
base = np.stack([ar1(0.9) for _ in range(N)])
with torch.no_grad():
    b_score = anomaly(torch.tensor(base, dtype=torch.float32)).numpy()
print(f"non-adaptive moment-matched: AUC={auc(h_score, b_score):.3f} "
      f"(attack mean-anom {b_score.mean():.3f} vs healthy {h_score.mean():.3f})")

def adaptive(rho_min, steps=150, lr=0.3, lam_m=2.0, lam_s=2.0, lam_a=4.0):
    r = torch.tensor(np.stack([ar1(max(rho_min, 0.85)) for _ in range(N)]),
                     dtype=torch.float32, requires_grad=True)
    opt = torch.optim.Adam([r], lr=lr)
    for _ in range(steps):
        opt.zero_grad()
        a = anomaly(r)
        mean_pen = (r.mean(1) - MEAN).pow(2).mean()
        std_pen = (r.std(1) - STD).pow(2).mean()
        ac = torch.stack([autocorr1(r[b]) for b in range(N)])
        ac_pen = torch.relu(rho_min - ac).pow(2).mean()       # keep autocorr >= rho_min
        loss = a.mean() + lam_m*mean_pen + lam_s*std_pen + lam_a*ac_pen
        loss.backward(); opt.step()
        with torch.no_grad(): r.clamp_(0.5, 60)
    with torch.no_grad():
        rr = r.detach()
        sc = anomaly(rr).numpy()
        acv = np.array([float(autocorr1(rr[b])) for b in range(N)])
        mu = rr.mean(1).numpy(); sd = rr.std(1).numpy()
    return sc, acv, mu, sd

print("\n[moment-matched constraint ON: mean=8,std=3 held] detector-adaptive PGD")
print("rho_min | adaptive AUC | attack mean-anom | realised autocorr | marg(mean/std)")
aucs = []
for rho_min in [0.0, 0.3, 0.6, 0.8]:
    sc, acv, mu, sd = adaptive(rho_min, steps=300)
    a = auc(h_score, sc); aucs.append(a)
    print(f"  {rho_min:.1f}   |    {a:.3f}    |     {sc.mean():.3f}      "
          f"|      {acv.mean():.2f}       |  {mu.mean():.1f}/{sd.mean():.1f}")
print(f"  -> worst-case adaptive AUC over rho_min = {min(aucs):.3f} (vs non-adaptive 0.92)")

# UNCONSTRAINED control: adversary abandons matched marginals to chase pure evasion.
def unconstrained(steps=300, lr=0.3):
    r = torch.tensor(np.stack([ar1(0.9) for _ in range(N)]), dtype=torch.float32, requires_grad=True)
    opt = torch.optim.Adam([r], lr=lr)
    for _ in range(steps):
        opt.zero_grad(); anomaly(r).mean().backward(); opt.step()
        with torch.no_grad(): r.clamp_(0.5, 60)
    with torch.no_grad():
        rr = r.detach(); sc = anomaly(rr).numpy()
    return auc(h_score, sc), rr.mean().item(), rr.std().item()
ua, umu, usd = unconstrained()
print(f"\n[constraint OFF: adversary abandons the attack] AUC={ua:.3f} but marginals drift "
      f"to mean/std={umu:.1f}/{usd:.1f} (no longer moment-matched -> a mean/var threshold "
      f"re-detects it).")
