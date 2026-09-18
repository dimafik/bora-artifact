"""Why the beta = 1.0 cell of the mimicry sweep is a property of the generator.

`run_adv.window()` injects  d = amp * |beta*c_hat + (1-beta)*e + 1.0| , so at
beta = 1 the independent component e vanishes and the injected delay becomes a
*deterministic* rectification of the cluster's own common mode. The attacked
node is then a folded function of a signal every healthy node follows affinely,
and that fold is visible to a closed-form fit with nothing trained.

Two such rules, scored on the SAME test windows E-G and E-H used (same seeds and
the same two warm-up build() calls, so the RNG stream matches):

  quad  max_i |c2| of the least-squares fit  z_i ~ 1 + lz_i + lz_i^2
  relu  max_i |c2| of                        z_i ~ 1 + lz_i + relu(-lz_i - 1)

`relu` uses the generator's own offset and is therefore informed by it; `quad`
is not, and still beats every advisor in results_adv2.json and
results_rules_sweep.json from beta = 0.75 up -- including the band where those
files report that every advisor fails. The run also prints the injected delay's
own mean and s.d., which run_adv's docstring calls constant in beta.

`corr_rule` is recomputed here as a control: it must reproduce the
results_rules_sweep.json column to three decimals, which is how we know the two
harnesses are reading the same data.

    python audit_beta_curvature.py        # a few minutes, numpy only
"""
import os, sys, json
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
os.chdir(HERE)
import run_adv as A
import models_v2 as MV
import run_rules_sweep as R

BETAS = [0.0, 0.25, 0.5, 0.6, 0.75, 0.8, 0.9, 1.0]
SEEDS = [0, 1, 2]
OUT = "audit_beta_curvature.json"


def _z(X):
    return (X - X.mean(2, keepdims=True)) / (X.std(2, keepdims=True) + 1e-9)


def _loo(z):
    n = z.shape[1]
    loo = (z.sum(1, keepdims=True) - z) / (n - 1)
    return (loo - loo.mean(2, keepdims=True)) / (loo.std(2, keepdims=True) + 1e-9)


def _fit_max(X, basis):
    """max over nodes of |third coefficient| of a per-window OLS. Nothing is
    fitted across windows, so the rule carries no trained parameter."""
    z = _z(X)
    lz = _loo(z)
    B, N, K = z.shape
    out = np.zeros((B, N))
    for b in range(B):
        for i in range(N):
            g = lz[b, i]
            D = np.c_[np.ones(K), g, basis(g)]
            coef, *_ = np.linalg.lstsq(D, z[b, i], rcond=None)
            out[b, i] = abs(coef[2])
    return out.max(1)


def rule_quad(X):
    return _fit_max(X, lambda g: g * g)


def rule_relu(X):
    return _fit_max(X, lambda g: np.maximum(-g - 1.0, 0.0))


def delay_stats(beta, seed, n=300):
    """mean and s.d. of the injected delay d itself, straight from the generator."""
    rng = np.random.default_rng(90000 + 1000 * seed + int(beta * 100))
    ds = []
    for _ in range(n):
        c = A.ar1(rng)
        ch = (c - c.mean()) / (c.std() + 1e-9)
        e = A.ar1(rng, rho=0.0)
        e = (e - e.mean()) / (e.std() + 1e-9)
        ds.append(1.2 * np.abs(beta * ch + (1 - beta) * e + 1.0))
    ds = np.concatenate(ds)
    return float(ds.mean()), float(ds.std())


def main():
    res = json.load(open(OUT)) if os.path.exists(OUT) else {}
    for beta in BETAS:
        for seed in SEEDS:
            key = "%.2f/seed%d" % (beta, seed)
            if key in res:
                continue
            rng = np.random.default_rng(1000 * seed + int(beta * 100))
            A.build(rng, 1000, beta)             # keep the stream aligned with E-G/E-H
            A.build(rng, 250, beta)
            Xte, yte = A.build(rng, 333, beta)
            dm, dsd = delay_stats(beta, seed)
            res[key] = {"corr_rule": float(MV.auc(yte, R.rule_corr(Xte))),
                        "quad_rule": float(MV.auc(yte, rule_quad(Xte))),
                        "relu_rule": float(MV.auc(yte, rule_relu(Xte))),
                        "delay_mean": dm, "delay_sd": dsd}
            json.dump(res, open(OUT, "w"), indent=1)
            print("beta %.2f seed %d  corr %.3f  quad %.3f  relu %.3f   delay %.3f +- %.3f"
                  % (beta, seed, res[key]["corr_rule"], res[key]["quad_rule"],
                     res[key]["relu_rule"], dm, dsd), flush=True)

    print("\n%-6s %-16s %-16s %-16s %-14s %-14s"
          % ("beta", "corr_rule", "quad_rule", "relu_rule", "delay mean", "delay sd"))
    for beta in BETAS:
        ks = ["%.2f/seed%d" % (beta, s) for s in SEEDS if "%.2f/seed%d" % (beta, s) in res]
        if not ks:
            continue
        row = [beta]
        for m in ("corr_rule", "quad_rule", "relu_rule", "delay_mean", "delay_sd"):
            v = [res[k][m] for k in ks]
            row.append("%.3f+-%.3f" % (np.mean(v), np.std(v, ddof=1) if len(v) > 1 else 0))
        print("%-6.2f %-16s %-16s %-16s %-14s %-14s" % tuple(row))


if __name__ == "__main__":
    main()
