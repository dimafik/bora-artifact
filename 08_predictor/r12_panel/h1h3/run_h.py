"""H1/H2/H3 as pre-registered on 2026-09-16 (리비전/PREREG_H1H3.md).

usage: python run_h.py smoke | pilot | h1 | h2 | h3 | all
Results accumulate in results.json; a finished (task, cond, model, seed) cell is
never recomputed, so the run can be resumed.
"""
import sys, json, os, time
import numpy as np
import torch
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline

import rel_gen as G
import rel_models as M

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
RES = "results.json"
BIG = False          # --big: the same task, a larger budget for every model
NETS = ["per-node", "deepsets", "relation", "gru-nodes", "attention"]
SEEDS = [0, 1, 2]
TRAIN, VAL, TEST = 1200, 400, 800
LR = {}          # filled by pilot, then fixed


def load():
    return json.load(open(RES)) if os.path.exists(RES) else {}


def save(r):
    json.dump(r, open(RES, "w"), indent=1)


def put(r, task, cond, model, seed, value):
    r.setdefault(task, {}).setdefault(cond, {}).setdefault(model, {})[str(seed)] = value
    save(r)


def have(r, task, cond, model, seed):
    return str(seed) in r.get(task, {}).get(cond, {}).get(model, {})


def T(a):
    return torch.tensor(a)


def hand_auc(Xtr, ytr, Xte, yte, groups):
    m = make_pipeline(StandardScaler(), LogisticRegression(max_iter=5000))
    m.fit(M.hand_features(Xtr, groups), ytr)
    return float(M.auc(yte, m.decision_function(M.hand_features(Xte, groups))))


def net_auc(rel, Xtr, ytr, Xva, yva, tests, seed, lr):
    torch.manual_seed(seed)
    net = M.Net(rel)
    ep, pat = (40, 6) if BIG else (15, 3)
    net, _ = M.fit(net, T(Xtr), T(ytr), T(Xva), T(yva), lr, epochs=ep, patience=pat)
    return {k: float(M.auc(y, M.scores(net, T(X)))) for k, (X, y) in tests.items()}


def data(fams, seed, n=5, npairs=None, regions=None, shuffle_test=False):
    tr, va, te = npairs or (TRAIN, VAL, TEST)
    if regions:
        Xtr, ytr = G.build_regions(tr, 100 + seed, regions)
        Xva, yva = G.build_regions(va, 200 + seed, regions)
        return (Xtr, ytr), (Xva, yva)
    Xtr, ytr = G.build(tr, 100 + seed, fams, n)
    Xva, yva = G.build(va, 200 + seed, fams, n)
    return (Xtr, ytr), (Xva, yva)


def run_pilot(r):
    """Learning rate per model, chosen on the F1 fold of H1, seed 0 only."""
    if "LR" in r:
        LR.update(r["LR"]); print("LR (cached)", LR); return
    fams = [f for f in G.FAMILIES if f != "F1_level"]
    (Xtr, ytr), (Xva, yva) = data(fams, 0)
    Xte, yte = G.build(TEST // 2, 300, ["F1_level"], 5)
    for rel in NETS:
        best = (None, -1)
        for lr in (3e-4, 1e-3):
            t0 = time.time()
            a = net_auc(rel, Xtr, ytr, Xva, yva, {"t": (Xte, yte)}, 0, lr)["t"]
            print("  pilot %-10s lr=%.0e val-selected test-auc=%.4f (%.1f min)" % (rel, lr, a, (time.time() - t0) / 60), flush=True)
            if a > best[1]:
                best = (lr, a)
        LR[rel] = best[0]
    r["LR"] = LR; save(r)
    print("LR", LR, flush=True)


def run_h1(r):
    for held in G.FAMILIES:
        fams = [f for f in G.FAMILIES if f != held]
        for seed in SEEDS:
            (Xtr, ytr), (Xva, yva) = data(fams, seed)
            Xte, yte = G.build(TEST, 300 + seed, [held], 5)
            if not have(r, "H1", held, "hand-fold", seed):
                put(r, "H1", held, "hand-fold", seed, hand_auc(Xtr, ytr, Xte, yte, fams))
            if not have(r, "H1", held, "hand-full", seed):
                put(r, "H1", held, "hand-full", seed, hand_auc(Xtr, ytr, Xte, yte, G.FAMILIES))
            for rel in NETS:
                if have(r, "H1", held, rel, seed):
                    continue
                t0 = time.time()
                a = net_auc(rel, Xtr, ytr, Xva, yva, {"t": (Xte, yte)}, seed, LR[rel])["t"]
                put(r, "H1", held, rel, seed, a)
                print("H1 held=%-10s %-10s seed=%d auc=%.4f (%.1f min)" % (held, rel, seed, a, (time.time() - t0) / 60), flush=True)


def run_h2(r):
    conds = {"3+2": (3, 2), "4+3": (4, 3), "6+5": (6, 5)}
    for seed in SEEDS:
        (Xtr, ytr), (Xva, yva) = data(None, seed, regions=(3, 2))
        tests = {k: G.build_regions(TEST // 2, 300 + seed, v) for k, v in conds.items()}
        for name, groups in (("hand-fold", ["F1_level", "F2_decorr"]), ("hand-full", G.FAMILIES)):
            for k, (Xte, yte) in tests.items():
                if not have(r, "H2", k, name, seed):
                    put(r, "H2", k, name, seed, hand_auc(Xtr, ytr, Xte, yte, groups))
        for rel in NETS:
            if all(have(r, "H2", k, rel, seed) for k in conds):
                continue
            t0 = time.time()
            out = net_auc(rel, Xtr, ytr, Xva, yva, tests, seed, LR[rel])
            for k, v in out.items():
                put(r, "H2", k, rel, seed, v)
            print("H2 %-10s seed=%d %s (%.1f min)" % (rel, seed, {k: round(v, 4) for k, v in out.items()}, (time.time() - t0) / 60), flush=True)


def run_h3(r):
    for seed in SEEDS:
        (Xtr, ytr), (Xva, yva) = data(G.FAMILIES, seed, 5)
        tests = {}
        for n in (5, 7, 11, 21):
            tests["N%d" % n] = G.build(TEST // 2, 300 + seed + n, G.FAMILIES, n)
            tests["N%d-shuf" % n] = G.build(TEST // 2, 300 + seed + n, G.FAMILIES, n, shuffle_nodes=True)
        for name, groups in (("hand-fold", G.FAMILIES), ("hand-full", G.FAMILIES)):
            if name == "hand-full":
                continue
            for k, (Xte, yte) in tests.items():
                if not have(r, "H3", k, name, seed):
                    put(r, "H3", k, name, seed, hand_auc(Xtr, ytr, Xte, yte, groups))
        for rel in NETS:
            if all(have(r, "H3", k, rel, seed) for k in tests):
                continue
            t0 = time.time()
            out = net_auc(rel, Xtr, ytr, Xva, yva, tests, seed, LR[rel])
            for k, v in out.items():
                put(r, "H3", k, rel, seed, v)
            print("H3 %-10s seed=%d %s (%.1f min)" % (rel, seed, {k: round(v, 3) for k, v in out.items()}, (time.time() - t0) / 60), flush=True)


def smoke():
    global TRAIN, VAL, TEST
    TRAIN, VAL, TEST = 60, 40, 60
    r = {}
    fams = [f for f in G.FAMILIES if f != "F2_decorr"]
    (Xtr, ytr), (Xva, yva) = data(fams, 0, npairs=(TRAIN, VAL, TEST))
    Xte, yte = G.build(TEST, 300, ["F2_decorr"], 5)
    print("shapes", Xtr.shape, Xte.shape, "balance", ytr.mean())
    print("hand-fold", round(hand_auc(Xtr, ytr, Xte, yte, fams), 3),
          "hand-full", round(hand_auc(Xtr, ytr, Xte, yte, G.FAMILIES), 3))
    for rel in NETS:
        t0 = time.time()
        a = net_auc(rel, Xtr, ytr, Xva, yva, {"t": (Xte, yte)}, 0, 1e-3)["t"]
        print("  %-10s auc=%.3f (%.2f min)" % (rel, a, (time.time() - t0) / 60), flush=True)


if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "smoke"
    if "--big" in sys.argv:
        BIG = True
        RES = "results_big.json"
        TRAIN, VAL, TEST = 3600, 800, 1200
        M.D = 32
        print("BIG budget: train=%d epochs=40 patience=6 width=%d" % (TRAIN, M.D), flush=True)
    if what == "smoke":
        smoke(); raise SystemExit
    r = load()
    run_pilot(r)
    if what in ("h1", "all"):
        run_h1(r)
    if what in ("h2", "all"):
        run_h2(r)
    if what in ("h3", "all"):
        run_h3(r)
    print("done", what)
