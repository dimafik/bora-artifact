"""Fairness check before any verdict.

E-D trained every torch model from scratch at lr = 1e-3.  That is the setting the
baselines were tuned at; the deployed Transformer was trained at 3e-4 with a warm
start.  A single shared learning rate can cripple one architecture, which is the
same error I corrected earlier when the MLP and CNN sat at chance for want of
input normalisation -- and it would be self-serving to leave it uncorrected only
where it happens to hurt our own model.

So: sweep the learning rate for all four torch models on H1 and on the hardest
H3 fold, and take each model's best.  If the Transformer still loses after being
given its own best setting, the result stands.
"""
import sys, json, time
sys.path.insert(0, "."); sys.path.insert(0, ".."); sys.path.insert(0, "../predictor")
import ed_run as E, hard_gen, gen

LRS = [3e-4, 1e-3, 3e-3]
out = {}
for task, fams in (("H1", None), ("H3_holdout_ar1", ["burst", "varshift", "heavytail"])):
    if task == "H1":
        Xtr, ytr, _ = hard_gen.build("H1", 10000, seed=101)
        Xva, yva, _ = hard_gen.build("H1", 1000, seed=202)
        Xte, yte, _ = hard_gen.build("H1", 2000, seed=303)
    else:
        Xtr, ytr, _ = hard_gen.build("H2", 10000, seed=401, families=fams)
        Xva, yva, _ = hard_gen.build("H2", 1000, seed=402, families=fams)
        Xte, yte, _ = hard_gen.build("H2", 2000, seed=403, families=["ar1"])
    print("=== %s" % task, flush=True)
    out[task] = {}
    for nm, net in E.make_nets(Xtr):
        best = (-1, None, None)
        for lr in LRS:
            _, netc = [p for p in E.make_nets(Xtr) if p[0] == nm][0]
            netc, ep = E.fit_torch(netc, Xtr, ytr, Xva, yva, 80, 10, lr=lr)
            a = gen.auc(yte.numpy(), E.score(netc, Xte))
            print("   %-20s lr=%.0e ep=%2d AUC=%.4f" % (nm, lr, ep, a), flush=True)
            if a > best[0]:
                best = (a, lr, ep)
        out[task][nm] = dict(best_auc=round(best[0], 4), lr=best[1], epochs=best[2])
        json.dump(out, open("lrsweep.json", "w"), indent=1)
print("done", flush=True)
