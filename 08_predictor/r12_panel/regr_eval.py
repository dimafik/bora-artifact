"""Regression checks, pulled forward and run separately.

The multi-node result is only usable if the added node-axis attention does not
cost anything on the single-node tasks the deployed model already does.  A layer
that helps one regime and hurts the other is not deployable, so this is the last
piece the verdict needs -- and it is cheap (N=1, no cross-node work), so it runs
beside the long E1 job rather than after it.

    H1b   a short attack segment inside a 60-tick window
    NA    the non-adaptive moment-matched detection the paper reports
"""
import sys, json, time, os
import numpy as np
import torch

sys.path.insert(0, "."); sys.path.insert(0, ".."); sys.path.insert(0, "../predictor")
import gen, ed2_run
from relational import RelationalScorePredictor, count
from final_eval import fit, auc_m, bce, wrap, VARIANTS, SEEDS

OUT = "regr_eval.json"


def task(name, seed):
    if name == "H1b-regr":
        tr = ed2_run.build_H1b(3000, 100 + seed)
        va = ed2_run.build_H1b(600, 200 + seed)
        te = ed2_run.build_H1b(1000, 300 + seed)
    else:
        tr = gen.make(3000, 100 + seed)[:2]
        va = gen.make(600, 200 + seed)[:2]
        te = gen.make(1000, 300 + seed)[:2]
    return wrap(tr[0]), tr[1], wrap(va[0]), va[1], (wrap(te[0]), te[1])


if __name__ == "__main__":
    res = json.load(open(OUT)) if os.path.exists(OUT) else {}
    for name in ("H1b-regr", "NA-regr"):
        res.setdefault(name, {})
        for var in VARIANTS:
            if var in res[name]:
                print("=== %s / %s (완료, 건너뜀)" % (name, var), flush=True)
                continue
            runs = []
            for sd in SEEDS:
                torch.manual_seed(sd)
                Xtr, ytr, Xva, yva, (Xte, yte) = task(name, sd)
                t = time.time()
                net = RelationalScorePredictor(relational=var)
                net, ep = fit(net, Xtr, ytr, Xva, yva, bce, auc_m)
                a = round(auc_m(net, Xte, yte), 4)
                runs.append(a)
                print("  %-9s %-10s seed=%d ep=%2d AUC=%.4f (%.1f min)"
                      % (name, var, sd, ep, a, (time.time() - t) / 60), flush=True)
            res[name][var] = dict(params=count(RelationalScorePredictor(relational=var)),
                                  runs=runs, mean=round(float(np.mean(runs)), 4),
                                  sd=round(float(np.std(runs)), 4))
            json.dump(res, open(OUT, "w"), indent=1)
            print("  -> %-9s %-10s %.4f±%.4f"
                  % (name, var, res[name][var]["mean"], res[name][var]["sd"]), flush=True)
    print("done", flush=True)
