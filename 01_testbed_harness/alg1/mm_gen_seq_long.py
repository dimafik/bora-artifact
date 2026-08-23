"""Generate per-node netem delay sequences for the live moment-matched
experiment. Baseline phase: all 5 nodes white-noise N(MEAN,STD). Attack phase:
o3 = AR(1) (same marginal mean/var, autocorrelated), others = white. Same
marginal => a mean/variance threshold cannot separate; only temporal structure
differs. Writes delays.csv (cols o1..o5 in ms) + meta (n_baseline)."""
import numpy as np, json
rng = np.random.default_rng(20260611)
MEAN, STD, RHO = 8.0, 3.0, 0.9
N_BASE, N_ATK = 120, 1920   # long campaign: >=31 non-overlapping K=60 in-attack windows

def white(n): return np.clip(rng.normal(MEAN, STD, n), 0.5, 60)
def ar1(n):
    x = np.empty(n); x[0] = rng.normal(MEAN, STD)
    e = rng.normal(0, STD*np.sqrt(1-RHO**2), n)
    for t in range(1, n): x[t] = MEAN + RHO*(x[t-1]-MEAN) + e[t]
    return np.clip(x, 0.5, 60)

cols = {}
for nid in [1, 2, 3, 4, 5]:
    base = white(N_BASE)
    atk = ar1(N_ATK) if nid == 3 else white(N_ATK)
    cols[nid] = np.concatenate([base, atk])
rows = N_BASE + N_ATK
with open(r"D:\fabric-d2\results\delays.csv", "w") as f:
    for t in range(rows):
        f.write(",".join(f"{cols[n][t]:.2f}" for n in [1,2,3,4,5]) + "\n")
json.dump({"n_baseline": N_BASE, "n_attack": N_ATK, "mean": MEAN, "std": STD, "rho": RHO},
          open(r"D:\fabric-d2\results\delays_meta.json", "w"))
# sanity: marginal moments of o3 attack vs o1 attack
a3 = cols[3][N_BASE:]; a1 = cols[1][N_BASE:]
print(f"o3 attack mean/std={a3.mean():.2f}/{a3.std():.2f}  o1 attack mean/std={a1.mean():.2f}/{a1.std():.2f}")
print(f"o3 lag-1 autocorr={np.corrcoef(a3[:-1],a3[1:])[0,1]:.2f}  o1 lag-1={np.corrcoef(a1[:-1],a1[1:])[0,1]:.2f}")
print(f"rows={rows} n_baseline={N_BASE}")
