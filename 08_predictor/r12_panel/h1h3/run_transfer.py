"""E-E: trained at one cluster size, deployed at another, on real telemetry.

Section III-G says the cluster is reconfigured while it runs, so an advisor that
has to be refitted when N changes is a deployment problem, not just a worse
detector. The daemon log has 18 independent N=7 segments with exactly one
orderer delayed and 2 such segments at N=9, so the transfer can be measured
without retraining: fit at N=7, score at N=9.

Task, as in run_real.py: which orderer is the delayed one (top-1, chance 1/N),
in the NORM regime where each node's window is standardised and only the
relation between nodes is left.
"""
import os, sys, json, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
import real_seg
import run_real as R
import hand_v2 as H
import numpy.linalg as la

SEEDS = [0, 1, 2]
RES = "results_transfer.json"


def hand_attr_fit(X, y, blocks=("base", "group")):
    """A conditional logit over per-node features, same idea as run_real.HandRank
    but with the richer v2 feature blocks reduced to per-node quantities."""
    return R.HandRank().fit(X, y)


def main():
    segs = real_seg.segments()
    s7 = [s for s in segs if len(s[0]) == 7 and len(s[1]) == 1]
    s9 = [s for s in segs if len(s[0]) == 9 and len(s[1]) == 1]
    print("segments: N=7 %d, N=9 %d" % (len(s7), len(s9)), flush=True)
    res = json.load(open(RES)) if os.path.exists(RES) else {}
    for mode in ("raw", "norm"):
        for seed in SEEDS:
            key = "%s/seed%d" % (mode, seed)
            rng = np.random.default_rng(seed)
            idx = rng.permutation(len(s7))
            tr = [s7[i] for i in idx[3:]]
            va = [s7[i] for i in idx[:3]]
            Xtr, ytr = R.make(tr, mode, 400, seed)
            Xva, yva = R.make(va, mode, 400, seed + 50)
            X9, y9 = R.make(s9, mode, 400, seed + 90)
            print("%s: train %s val %s  N=9 test %s" % (key, Xtr.shape, Xva.shape, X9.shape), flush=True)
            if res.get(key, {}).get("hand") is None:
                h = R.HandRank().fit(Xtr, ytr)
                res.setdefault(key, {})["hand"] = R.top1(h.score(X9), y9)
                res[key]["hand_in_domain"] = R.top1(h.score(Xva), yva)
                res[key]["chance_N9"] = 1.0 / 9
                json.dump(res, open(RES, "w"), indent=1)
                print("   hand   N9 %.3f (in-domain N7 %.3f)" % (res[key]["hand"], res[key]["hand_in_domain"]), flush=True)
            for rel in ("per-node", "deepsets", "relation", "attention"):
                if res.get(key, {}).get(rel) is not None:
                    continue
                t0 = time.time()
                net = R.fit_net(rel, Xtr, ytr, Xva, yva, 3e-4, 25, 5)
                res.setdefault(key, {})[rel] = R.top1(R.predict(net, X9), y9)
                res[key][rel + "_in_domain"] = R.top1(R.predict(net, Xva), yva)
                json.dump(res, open(RES, "w"), indent=1)
                print("   %-10s N9 %.3f (in-domain N7 %.3f)  (%.1f min)" %
                      (rel, res[key][rel], res[key][rel + "_in_domain"], (time.time() - t0) / 60), flush=True)
    print("\nE-E summary: top-1 at N=9 after training at N=7 only")
    for mode in ("raw", "norm"):
        ks = [k for k in res if k.startswith(mode)]
        for m in ("hand", "per-node", "deepsets", "relation", "attention"):
            v = [res[k][m] for k in ks if res[k].get(m) is not None]
            d = [res[k][m + "_in_domain"] for k in ks if res[k].get(m + "_in_domain") is not None]
            if v:
                print("  %-5s %-10s N9 %.3f +- %.3f   (N7 in-domain %.3f)" %
                      (mode, m, np.mean(v), np.std(v, ddof=1) if len(v) > 1 else 0, np.mean(d) if d else float("nan")))


if __name__ == "__main__":
    main()
