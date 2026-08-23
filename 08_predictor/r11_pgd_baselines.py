"""R1-1, part 2: do the lightweight detectors survive the adaptive adversary?

`r11_necessity_baselines.py` showed that on the paper's own necessity benchmark a
LINEAR classifier over 40 per-channel summary statistics reaches AUC 0.981,
beating the deployed Transformer's 0.93 with ~40 parameters instead of 141,067.
Taken alone that says attention is not required, and it is the honest reading of
the non-adaptive regime.

But the paper's other adversary is white-box: `mm_adaptive.py` runs PGD on the
injected delay sequence to minimise the detector's own anomaly head, subject to
matched marginals (mean 8 / std 3) and a floor on lag-1 autocorrelation, and the
Transformer holds at worst 0.733 across the rho_min sweep. Nobody has run that
attack against the lightweight rivals. If a 40-parameter statistic collapses when
the adversary can see it, the architecture claim is restored on the axis that
actually matters for a security system; if it holds, the honest move is to drop
the architecture-necessity framing entirely.

Same protocol as `mm_adaptive.py` so the numbers land in one table:

    healthy  r ~ iid N(8,3)                       window built by window_t()
    attack   r ~ AR(1) rho=0.9, same marginals
    PGD      300 Adam steps, lr 0.3, penalties lam_m=2 lam_s=2 lam_a=4,
             rho_min in {0.0, 0.3, 0.6, 0.8}, clamp [0.5, 60]

The detectors are trained in torch rather than sklearn so the attack is exact
white-box gradient descent on the deployed decision function, not a transfer
attack. `r11_mm_baselines.py` confirmed this reconstruction: best_mm.pt scores
0.935 here against the 0.923 the paper reports.

    python r11_pgd_baselines.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
OUT = HERE / "r11_pgd_baselines.json"

K = 60
ALPHA = 0.8
MEAN, STD = 8.0, 3.0
N_ATK = 1000                   # mm_adaptive.py uses 200; AUC noise there is +-0.03
N_SEEDS = 5
RHO_MINS = [0.0, 0.3, 0.6, 0.8]

rng = np.random.default_rng(0)


def reseed(s):
    """Re-seed both generators so a repeat varies the traces, the detector
    initialisation and the attack together -- the spread then covers training
    variance, not just sampling variance."""
    global rng
    rng = np.random.default_rng(s)
    torch.manual_seed(s)

# --- constant channels, exactly as mm_adaptive.window_t builds them -----------
_CC = np.convolve(np.ones(K), np.ones(20) / 20, mode="same")
CC_T = torch.tensor(_CC, dtype=torch.float32)
DCC_T = torch.tensor(np.diff(_CC, prepend=_CC[0]), dtype=torch.float32)
CC_T1 = torch.ones(K)
TC_T = torch.full((K,), 100.0)
DZ_T = torch.zeros(K)


def window_t(r):
    """(B,K) raw delays -> (B,K,8) window. Batched form of mm_adaptive.window_t."""
    B = r.shape[0]
    rtt = [r[:, 0]]
    for t in range(1, K):
        rtt.append(ALPHA * rtt[-1] + (1 - ALPHA) * r[:, t])
    RTT = torch.stack(rtt, dim=1)
    dRTT = torch.cat([RTT[:, :1] * 0, RTT[:, 1:] - RTT[:, :-1]], dim=1)
    rep = lambda v: v.unsqueeze(0).expand(B, K)          # noqa: E731
    return torch.stack([rep(CC_T1), rep(CC_T), r, RTT, rep(TC_T),
                        rep(DCC_T), dRTT, rep(DZ_T)], dim=2)


def ar1(n, rho):
    x = np.empty((n, K))
    x[:, 0] = rng.normal(MEAN, STD, n)
    e = rng.normal(0, STD * np.sqrt(1 - rho ** 2), (n, K))
    for t in range(1, K):
        x[:, t] = MEAN + rho * (x[:, t - 1] - MEAN) + e[:, t]
    return np.clip(x, 0.5, 60)


def white(n):
    return np.clip(rng.normal(MEAN, STD, (n, K)), 0.5, 60)


def autocorr1(r):
    """Lag-1 autocorrelation, per row, differentiable."""
    rc = r - r.mean(1, keepdim=True)
    return (rc[:, :-1] * rc[:, 1:]).sum(1) / (rc.pow(2).sum(1) + 1e-8)


def auc(neg, pos):
    neg, pos = np.asarray(neg), np.asarray(pos)
    return float(sum(np.sum(p > neg) + 0.5 * np.sum(p == neg) for p in pos)
                 / (len(pos) * len(neg)))


# --- differentiable feature maps ---------------------------------------------
def summary_feats(X):
    """Per-channel mean/std/min/max/slope: the statistics Table II searches over,
    handed to the model jointly. 40 numbers for 8 channels."""
    tc = torch.arange(K, dtype=torch.float32) - (K - 1) / 2.0
    denom = (tc * tc).sum()
    return torch.cat([X.mean(1), X.std(1), X.amin(1), X.amax(1),
                      (X * tc[None, :, None]).sum(1) / denom], dim=1)


def flat_feats(X):
    return X.reshape(X.shape[0], -1)


class Detector(torch.nn.Module):
    """A lightweight rival. `featfn` maps the window to what the model sees;
    inputs are standardised by statistics frozen at training time so the attack
    differentiates through exactly the deployed decision function."""

    def __init__(self, featfn, hidden=None):
        super().__init__()
        self.featfn = featfn
        self.hidden = hidden
        self.net = None

    def _build(self, d):
        if self.hidden is None:
            self.net = torch.nn.Linear(d, 1)
        else:
            h1, h2 = self.hidden
            self.net = torch.nn.Sequential(
                torch.nn.Linear(d, h1), torch.nn.ReLU(),
                torch.nn.Linear(h1, h2), torch.nn.ReLU(),
                torch.nn.Linear(h2, 1))

    def fit(self, X, y, epochs=300, lr=1e-2):
        with torch.no_grad():
            F = self.featfn(X)
            self.mu, self.sd = F.mean(0), F.std(0) + 1e-6
        self._build(F.shape[1])
        opt = torch.optim.Adam(self.parameters(), lr=lr)
        lossfn = torch.nn.BCEWithLogitsLoss()
        Fz = (F - self.mu) / self.sd
        for _ in range(epochs):
            opt.zero_grad()
            lossfn(self.net(Fz).squeeze(1), y).backward()
            opt.step()
        for p in self.parameters():
            p.requires_grad_(False)
        return self

    def logit(self, X):
        return self.net(((self.featfn(X) - self.mu) / self.sd)).squeeze(1)

    def n_params(self):
        return sum(p.numel() for p in self.parameters())


class DRTTStd(torch.nn.Module):
    """The single statistic that separates this benchmark without training:
    the within-window standard deviation of dRTT. Sign is fixed so that larger
    means more suspicious. Zero learned parameters."""

    def n_params(self):
        return 0

    def logit(self, X):
        return -X[:, :, 6].std(1)


def project_marginals(r):
    """Force every row to mean 8 / std 3 exactly. Clamping to the physical delay
    range perturbs this slightly, so rescale, clamp, rescale."""
    for _ in range(2):
        r = (r - r.mean(1, keepdim=True)) / (r.std(1, keepdim=True) + 1e-8) * STD + MEAN
        r = r.clamp(0.5, 60)
    return r


def project_autocorr(r, rho_min, r_hi, iters=20):
    """Blend rows that fell below the autocorrelation floor back toward a strongly
    correlated reference until they clear it. Lag-1 autocorrelation is monotone in
    the blend weight, so a bisection on that weight lands on the constraint
    boundary: the weakest attack that still satisfies rho_min."""
    if rho_min <= 0:
        return project_marginals(r)
    lo = torch.zeros(r.shape[0], 1)
    hi = torch.ones(r.shape[0], 1)
    for _ in range(iters):
        mid = (lo + hi) / 2
        ok = autocorr1(project_marginals((1 - mid) * r + mid * r_hi)) >= rho_min
        ok = ok.unsqueeze(1)
        hi = torch.where(ok, mid, hi)
        lo = torch.where(ok, lo, mid)
    return project_marginals((1 - hi) * r + hi * r_hi)


def pgd(det, rho_min, scale, steps=300, lr=0.3, lam_a=10.0):
    """mm_adaptive.adaptive(), retargeted at an arbitrary detector and made
    scale-free. Two changes are needed for the comparison to mean anything:

    (a) the marginal constraint is a PROJECTION, not a penalty. With penalties the
        adversary simply walks out of the constraint set whenever the detector's
        logits are large -- the linear model's attack drifted to std 5.1 and the
        MLP's to 8.6, which is the paper's own "constraint OFF" control, not a
        moment-matched attack.
    (b) the logit is divided by its spread on healthy traffic, so one lam_a means
        the same pressure against a 41-parameter model and a 141k-parameter one.

    The autocorrelation floor is likewise enforced by projection at the end."""
    r_hi = torch.tensor(ar1(N_ATK, 0.95), dtype=torch.float32)
    r = torch.tensor(ar1(N_ATK, max(rho_min, 0.85)), dtype=torch.float32)
    r = project_marginals(r).requires_grad_(True)
    opt = torch.optim.Adam([r], lr=lr)
    for _ in range(steps):
        opt.zero_grad()
        a = det.logit(window_t(r)) / scale
        ac_pen = torch.relu(rho_min - autocorr1(r)).pow(2).mean()
        (a.mean() + lam_a * ac_pen).backward()
        opt.step()
        with torch.no_grad():
            r.data = project_marginals(r.data)
    with torch.no_grad():
        rr = project_autocorr(r.detach(), rho_min, r_hi)
        return (det.logit(window_t(rr)).numpy(), autocorr1(rr).numpy(),
                rr.mean(1).numpy(), rr.std(1).numpy())


def run_once(seed):
    reseed(seed)
    # training set: the non-adaptive protocol both sides are fitted on
    n_tr = 2000
    Xtr = window_t(torch.tensor(np.concatenate([white(n_tr), ar1(n_tr, 0.9)]),
                                dtype=torch.float32))
    ytr = torch.cat([torch.zeros(n_tr), torch.ones(n_tr)])

    dets = {
        "linear / 40 summary stats": Detector(summary_feats).fit(Xtr, ytr),
        "MLP 64-32 / flattened window": Detector(flat_feats, hidden=(64, 32)).fit(Xtr, ytr),
        "std(dRTT) threshold (0 params)": DRTTStd(),
    }

    try:
        sys.path.insert(0, str(HERE / "predictor"))
        from model import ScorePredictor, CONFIG        # noqa: E402
        net = ScorePredictor(CONFIG)
        sd = torch.load(HERE / "best_mm.pt", map_location="cpu")
        net.load_state_dict(sd["model_state_dict"] if isinstance(sd, dict)
                            and "model_state_dict" in sd else sd)
        net.eval()
        for p in net.parameters():
            p.requires_grad_(False)

        class Ref(torch.nn.Module):
            def n_params(self):
                return sum(p.numel() for p in net.parameters())

            def logit(self, X):
                return net(X)["anomaly"].squeeze(1)

        dets["Transformer (best_mm.pt)"] = Ref()
    except Exception as exc:                            # noqa: BLE001
        print("reference NOT loaded: %s: %s" % (type(exc).__name__, exc))

    healthy = window_t(torch.tensor(white(N_ATK), dtype=torch.float32))
    base = window_t(torch.tensor(ar1(N_ATK, 0.9), dtype=torch.float32))

    out = {}
    for name, det in dets.items():
        with torch.no_grad():
            h = det.logit(healthy).numpy()
            b = det.logit(base).numpy()
        a0 = auc(h, b)
        scale = float(np.std(np.concatenate([h, b]))) + 1e-8
        sweep, cons = [], []
        for rm in RHO_MINS:
            sc, acv, mu, sdv = pgd(det, rm, scale)
            sweep.append(auc(h, sc))
            cons.append((float(acv.mean()), float(mu.mean()), float(sdv.mean())))
        out[name] = dict(params=det.n_params(), non_adaptive=a0,
                         sweep=sweep, worst_case=min(sweep), cons=cons)
        print("  seed %d  %-32s non-adapt %.3f  worst %.3f"
              % (seed, name, a0, min(sweep)))
    return out


def main():
    runs = [run_once(s) for s in range(N_SEEDS)]
    names = list(runs[0].keys())

    def ms(vals):
        return float(np.mean(vals)), float(np.std(vals))

    print("\n" + "=" * 78)
    print("  N=%d per class, %d seeds, mean +- sd" % (N_ATK, N_SEEDS))
    print("=" * 78)
    hdr = "  %-32s %7s %8s " % ("detector", "params", "non-adap")
    hdr += " ".join("%11s" % ("rho>=%.1f" % r) for r in RHO_MINS) + "%12s" % "worst"
    print(hdr)
    summary = {}
    for n in names:
        p = runs[0][n]["params"]
        na = ms([r[n]["non_adaptive"] for r in runs])
        sw = [ms([r[n]["sweep"][i] for r in runs]) for i in range(len(RHO_MINS))]
        wc = ms([r[n]["worst_case"] for r in runs])
        line = "  %-32s %7d %8s " % (n, p, "%.3f" % na[0])
        line += " ".join("%5.3f+-%.3f" % s for s in sw)
        line += "  %5.3f+-%.3f" % wc
        print(line)
        summary[n] = dict(params=p,
                          non_adaptive=[round(na[0], 4), round(na[1], 4)],
                          sweep={("rho_min_%.1f" % RHO_MINS[i]):
                                 [round(sw[i][0], 4), round(sw[i][1], 4)]
                                 for i in range(len(RHO_MINS))},
                          worst_case=[round(wc[0], 4), round(wc[1], 4)])

    # constraint audit: the table is only meaningful if every attack actually
    # stayed inside the moment-matched, autocorrelated set it claims to be in
    print("\n  constraint audit (worst deviation over all detectors and seeds)")
    for i, rm in enumerate(RHO_MINS):
        ac = min(r[n]["cons"][i][0] for r in runs for n in names)
        mu = [r[n]["cons"][i][1] for r in runs for n in names]
        sd = [r[n]["cons"][i][2] for r in runs for n in names]
        print("    rho_min %.1f: min realised autocorr %.3f | mean %.2f-%.2f | std %.2f-%.2f"
              % (rm, ac, min(mu), max(mu), min(sd), max(sd)))

    OUT.write_text(json.dumps(dict(n_per_class=N_ATK, n_seeds=N_SEEDS,
                                   rho_mins=RHO_MINS, summary=summary),
                              indent=2), encoding="utf-8")
    print("\nwrote", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main())
