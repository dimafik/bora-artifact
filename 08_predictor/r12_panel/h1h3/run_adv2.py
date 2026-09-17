"""E-G confirmation: the mimicry sweep over three seeds, with the curve filled in.

The first pass ran one seed per beta and found the defenders swapping places: at
beta 0.5 everything fails, at beta >= 0.9 the hand bank stays down while the
network recovers. Both ends of that need more than one seed before anything is
claimed, and the middle needs filling, so this re-runs betas
0.5 / 0.6 / 0.75 / 0.8 / 0.9 / 1.0 with three seeds each. Data, initialisation
and the test split all change with the seed. Every cell is written as it lands,
so the run resumes.
"""
import os, sys, json, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
import run_adv as A
import hand_v2 as H
import models_v2 as MV

BETAS = [0.5, 0.6, 0.75, 0.8, 0.9, 1.0]
SEEDS = [0, 1, 2]
PAIRS, EPOCHS = 1000, 35
RES = "results_adv2.json"


def cell(beta, seed):
    rng = np.random.default_rng(1000 * seed + int(beta * 100))
    Xtr, ytr = A.build(rng, PAIRS, beta)
    Xva, yva = A.build(rng, PAIRS // 4, beta)
    Xte, yte = A.build(rng, PAIRS // 3, beta)
    out = {}
    t0 = time.time()
    out["hand"] = A.auc_hand(A.fit_hand(Xtr, ytr), Xte, yte)
    for rel in ("attention", "deepsets"):
        net = A.fit_net(Xtr, ytr, Xva, yva, EPOCHS, rel)
        out[rel] = float(MV.auc(yte, MV.predict(net, Xte)))
    out["minutes"] = round((time.time() - t0) / 60, 1)
    return out


def main():
    res = json.load(open(RES)) if os.path.exists(RES) else {}
    for beta in BETAS:
        for seed in SEEDS:
            key = "%.2f/seed%d" % (beta, seed)
            if key in res:
                continue
            res[key] = cell(beta, seed)
            json.dump(res, open(RES, "w"), indent=1)
            print("beta %.2f seed %d  hand %.3f  attention %.3f  deepsets %.3f  (%.1f min)"
                  % (beta, seed, res[key]["hand"], res[key]["attention"],
                     res[key]["deepsets"], res[key]["minutes"]), flush=True)
    print("\nE-G confirmed (mean +- sd over 3 seeds)")
    print("%-8s %-16s %-16s %-16s" % ("beta", "hand bank", "attention", "deepsets"))
    for beta in BETAS:
        ks = ["%.2f/seed%d" % (beta, s) for s in SEEDS if "%.2f/seed%d" % (beta, s) in res]
        row = [beta]
        for m in ("hand", "attention", "deepsets"):
            v = [res[k][m] for k in ks]
            row.append("%.3f +- %.3f" % (np.mean(v), np.std(v, ddof=1) if len(v) > 1 else 0))
        print("%-8.2f %-16s %-16s %-16s" % tuple(row))


if __name__ == "__main__":
    main()
