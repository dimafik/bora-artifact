"""E-H: where each advisor stops working as the attacker hides its delay.

E-G swept the mimicry level for the hand bank and two networks. The advisors the
paper actually offers as alternatives were missing from that sweep: the
zero-parameter mean-RTT threshold that ran the closed loop over 480 forced
elections, and the MAD rule that matched the Transformer on the real feeds. They
are the ones a reviewer means by "a lightweight model", so the sweep has to
include them before anything is claimed about when a learned advisor earns its
place.

Rules are scored, not trained, so each is evaluated on the same test windows the
trained defenders saw at each beta, over the same three seeds.
"""
import os, sys, json
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
import run_adv as A

BETAS = [0.0, 0.25, 0.5, 0.6, 0.75, 0.8, 0.9, 1.0]
SEEDS = [0, 1, 2]
RES = "results_rules_sweep.json"


def auc(y, s):
    import models_v2 as MV
    return float(MV.auc(y, s))


def rule_threshold(X):
    """The deployed alternative: a node's mean RTT against the cluster's.
    On per-node standardised windows the mean is zero by construction, so the
    rule reads what it can still see -- dispersion against the cluster's."""
    sd = X.std(2)
    return (sd.max(1) - np.median(sd, 1)) / (np.median(sd, 1) + 1e-9)


def rule_mad(X):
    """E-B's relational rule: deviation from the peers in MADs, worst node."""
    sd = X.std(2)
    med = np.median(sd, 1, keepdims=True)
    mad = np.median(np.abs(sd - med), 1, keepdims=True) + 1e-9
    return ((sd - med) / mad).max(1)


def rule_corr(X):
    """A zero-parameter relational statistic: the lowest agreement any node has
    with the others (the cheapest form of the hand bank)."""
    z = (X - X.mean(2, keepdims=True)) / (X.std(2, keepdims=True) + 1e-9)
    N, K = X.shape[1], X.shape[2]
    loo = (z.sum(1, keepdims=True) - z) / (N - 1)
    lz = (loo - loo.mean(2, keepdims=True)) / (loo.std(2, keepdims=True) + 1e-9)
    return -(z * lz).mean(2).min(1)


RULES = {"threshold_rule": rule_threshold, "mad_rule": rule_mad, "corr_rule": rule_corr}


def main():
    res = json.load(open(RES)) if os.path.exists(RES) else {}
    for beta in BETAS:
        for seed in SEEDS:
            key = "%.2f/seed%d" % (beta, seed)
            if key in res:
                continue
            rng = np.random.default_rng(1000 * seed + int(beta * 100))
            A.build(rng, 1000, beta)                 # keep the stream aligned with E-G
            A.build(rng, 250, beta)
            Xte, yte = A.build(rng, 333, beta)
            res[key] = {n: auc(yte, f(Xte)) for n, f in RULES.items()}
            json.dump(res, open(RES, "w"), indent=1)
            print("beta %.2f seed %d  %s" % (beta, seed, {k: round(v, 3) for k, v in res[key].items()}), flush=True)
    print("\nE-H zero-parameter rules over the mimicry sweep (3 seeds)")
    print("%-8s %-18s %-18s %-18s" % ("beta", "threshold rule", "MAD rule", "corr rule"))
    for beta in BETAS:
        ks = ["%.2f/seed%d" % (beta, s) for s in SEEDS if "%.2f/seed%d" % (beta, s) in res]
        row = [beta]
        for n in RULES:
            v = [res[k][n] for k in ks]
            row.append("%.3f +- %.3f" % (np.mean(v), np.std(v, ddof=1) if len(v) > 1 else 0))
        print("%-8.2f %-18s %-18s %-18s" % tuple(row))


if __name__ == "__main__":
    main()
