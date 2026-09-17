"""T1/T2 with equal-budget random search for every family.

Protocol (fixed before the run):
  * 12 configurations per family, drawn from the same-sized space
  * the search sees the validation split only; the test split is scored once,
    with the configuration validation picked
  * the winner is then re-measured on 3 fresh seeds (data and init both change)
  * every configuration and its validation score is written to the results file,
    so the search is inspectable, not just its winner

usage: python run_t12.py T1|T2 [--trials 12] [--quick]
"""
import os, sys, json, time
import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
import t12_gen as G
import models_v2 as M
import hand_v2 as H

NETS = ["per-node", "deepsets", "gru-nodes", "relation", "attention"]
TRAIN, VAL, TEST = 1500, 600, 1000


def data(task, seed, npairs=None):
    tr, va, te = npairs or (TRAIN, VAL, TEST)
    return (G.build(task, tr, 1000 + seed), G.build(task, va, 2000 + seed),
            G.build(task, te, 3000 + seed))


def search_hand(Xtr, ytr, Xva, yva, Xte, yte, trials, rng, log):
    best = (None, -1)
    for i in range(trials):
        blocks = H.SETS[int(rng.integers(len(H.SETS)))]
        clf = H.CLFS[int(rng.integers(len(H.CLFS)))]
        m = H.make_clf(clf, rng)
        Ftr, Fva = H.features(Xtr, blocks), H.features(Xva, blocks)
        m.fit(Ftr, ytr)
        a = M.auc(yva, H.score(m, Fva))
        log.append(dict(model="hand", trial=i, cfg=dict(blocks=blocks, clf=clf), val=float(a)))
        print("   hand   trial%02d %-28s val %.4f" % (i, "%s/%s" % ("+".join(blocks), clf), a), flush=True)
        if a > best[1]:
            best = ((blocks, clf, m), a)
    blocks, clf, m = best[0]
    return dict(cfg=dict(blocks=blocks, clf=clf), val=float(best[1]),
                test=float(M.auc(yte, H.score(m, H.features(Xte, blocks)))))


def search_net(rel, Xtr, ytr, Xva, yva, Xte, yte, trials, rng, log, epochs, patience):
    best = (None, -1, None)
    for i in range(trials):
        cfg = M.sample_cfg(rng)
        t0 = time.time()
        net, val = M.fit(rel, cfg, Xtr, ytr, Xva, yva, seed=i, max_epochs=epochs, patience=patience)
        log.append(dict(model=rel, trial=i, cfg=cfg, val=float(val)))
        print("   %-10s trial%02d d%-3d L%d h%d lr%.0e drop%.1f val %.4f (%.1f min)"
              % (rel, i, cfg["d"], cfg["layers"], cfg["heads"], cfg["lr"], cfg["drop"], val,
                 (time.time() - t0) / 60), flush=True)
        if val > best[1]:
            best = (cfg, val, net)
    cfg, val, net = best
    return dict(cfg=cfg, val=float(val), test=float(M.auc(yte, M.predict(net, Xte))))


def confirm(task, rel, cfg, seeds, epochs, patience):
    out = []
    for s in seeds:
        (Xtr, ytr), (Xva, yva), (Xte, yte) = data(task, 100 + s)
        if rel == "hand":
            m = H.make_clf(cfg["clf"], np.random.default_rng(s))
            m.fit(H.features(Xtr, cfg["blocks"]), ytr)
            out.append(float(M.auc(yte, H.score(m, H.features(Xte, cfg["blocks"])))))
        else:
            net, _ = M.fit(rel, cfg, Xtr, ytr, Xva, yva, seed=s, max_epochs=epochs, patience=patience)
            out.append(float(M.auc(yte, M.predict(net, Xte))))
        print("   confirm %-10s seed%d %.4f" % (rel, s, out[-1]), flush=True)
    return out


def main():
    task = sys.argv[1] if len(sys.argv) > 1 else "T1"
    quick = "--quick" in sys.argv
    trials = 3 if quick else int(sys.argv[sys.argv.index("--trials") + 1]) if "--trials" in sys.argv else 12
    epochs, patience = (6, 3) if quick else (40, 8)
    global TRAIN, VAL, TEST
    if quick:
        TRAIN, VAL, TEST = 300, 200, 300
    res_path = "results_%s.json" % task
    res = json.load(open(res_path)) if os.path.exists(res_path) else {"search": [], "winner": {}, "confirm": {}}
    (Xtr, ytr), (Xva, yva), (Xte, yte) = data(task, 0)
    print("%s search data %s / %s / %s" % (task, Xtr.shape, Xva.shape, Xte.shape), flush=True)
    rng = np.random.default_rng(7)
    for fam in ["hand"] + NETS:
        if fam in res["winner"]:
            continue
        if fam == "hand":
            res["winner"][fam] = search_hand(Xtr, ytr, Xva, yva, Xte, yte, trials, rng, res["search"])
        else:
            res["winner"][fam] = search_net(fam, Xtr, ytr, Xva, yva, Xte, yte, trials, rng,
                                            res["search"], epochs, patience)
        json.dump(res, open(res_path, "w"), indent=1)
        print("  -> %-10s val %.4f test %.4f" % (fam, res["winner"][fam]["val"], res["winner"][fam]["test"]), flush=True)
    seeds = [1] if quick else [1, 2, 3]
    for fam in ["hand"] + NETS:
        if fam in res["confirm"]:
            continue
        res["confirm"][fam] = confirm(task, fam, res["winner"][fam]["cfg"], seeds, epochs, patience)
        json.dump(res, open(res_path, "w"), indent=1)
    print("\n%s summary (test of the validation-selected config, then 3 fresh seeds)" % task)
    for fam in ["hand"] + NETS:
        c = res["confirm"][fam]
        print("  %-10s test %.3f   confirm %.3f +- %.3f" %
              (fam, res["winner"][fam]["test"], float(np.mean(c)),
               float(np.std(c, ddof=1)) if len(c) > 1 else 0.0))
    json.dump(res, open(res_path, "w"), indent=1)


if __name__ == "__main__":
    main()
