"""E1+E2+E3 combined: the evaluation as a sceptical reviewer would want it.

Three things were missing from the earlier multi-node results, and each is an
objection a reviewer would raise:

  E3  "attention is not the only permutation-invariant operator."  DeepSets --
      every node sees the cross-node mean, no pairwise term -- is the canonical
      alternative.  If broadcasting the mean is enough, attention is not needed,
      and that has to be measured rather than assumed.
  E2  "the gaps are within noise."  Every number here is 5 seeds, reported as
      mean +/- sd.  Some earlier margins were 0.013 on a single run.
  E1  "the task is synthetic and built to suit attention."  The daemon logged
      two months of real per-node RTT from the Fabric testbed, so the same
      question is asked again with nothing synthetic: at N=7, one delayed node
      versus two, 3,374 windows a class, in two conditions --
        RAW   absolute level kept: this is deployment as it stands
        NORM  each node normalised: the cue a moment-matched adversary deletes

Regression checks (single-node H1b and non-adaptive detection) are included
because a relational layer that helps multi-node work and hurts the rest is not
deployable.  They are reported whichever way they fall.

Learning rate fixed to 3e-4 for every variant, chosen from the earlier sweep
where it was best or tied for both the control and the relational model.
"""
import sys, json, time, copy, os
import numpy as np
import torch
import torch.nn as nn

sys.path.insert(0, "."); sys.path.insert(0, ".."); sys.path.insert(0, "../predictor")
import gen, ed_run as E
import r2_run, d1_run, d2_run, ed2_run, real_data
from relational import RelationalScorePredictor, count

VARIANTS = ["none", "deepsets", "attention"]
SEEDS = [0, 1, 2, 3, 4]
LR = 3e-4
OUT = "final_eval.json"


def fit(net, Xtr, ytr, Xva, yva, loss, metric, epochs=20, patience=4, bs=32):
    opt = torch.optim.Adam(net.parameters(), lr=LR)
    best, state, bad = -1.0, None, 0
    for ep in range(epochs):
        net.train()
        perm = torch.randperm(len(Xtr))
        for i in range(0, len(Xtr), bs):
            idx = perm[i:i + bs]
            opt.zero_grad()
            loss(net(Xtr[idx]), ytr[idx]).backward()
            opt.step()
        a = metric(net, Xva, yva)
        if a > best + 1e-4:
            best, state, bad = a, copy.deepcopy(net.state_dict()), 0
        else:
            bad += 1
            if bad >= patience:
                break
    net.load_state_dict(state); net.eval()
    return net, ep + 1


def scores(net, X, bs=32):
    net.eval(); o = []
    with torch.no_grad():
        for i in range(0, len(X), bs):
            o.append(net(X[i:i + bs]).max(1).values)
    return torch.cat(o).numpy()


def auc_m(net, X, y): return gen.auc(y.numpy(), scores(net, X))


def top1(net, X, y, bs=64):
    net.eval(); ok = 0
    with torch.no_grad():
        for i in range(0, len(X), bs):
            ok += (net(X[i:i + bs]).argmax(1) == y[i:i + bs]).sum().item()
    return ok / len(X)


bce = lambda o, t: nn.functional.binary_cross_entropy_with_logits(o.max(1).values, t)
ce = lambda o, t: nn.functional.cross_entropy(o, t)
wrap = lambda X: X.unsqueeze(1)


def split(X, y, seed, frac=(0.7, 0.15)):
    g = np.random.default_rng(seed)
    idx = g.permutation(len(X))
    a, b = int(len(X) * frac[0]), int(len(X) * (frac[0] + frac[1]))
    s = lambda i: (X[idx[i]], y[idx[i]])
    return s(slice(0, a)), s(slice(a, b)), s(slice(b, None))


def make_task(name, seed):
    """-> (Xtr,ytr, Xva,yva, tests{}, loss, metric)"""
    if name == "R2b-synth":
        return (*r2_run.build(1500, 100 + seed), *r2_run.build(400, 200 + seed),
                {"": r2_run.build(800, 300 + seed)}, bce, auc_m)
    if name == "D1b-attr-synth":
        return (*d1_run.build(4000, 100 + seed), *d1_run.build(800, 200 + seed),
                {"": d1_run.build(1500, 300 + seed)}, ce, top1)
    if name == "D2b-varN-synth":
        return (*d2_run.build(2500, 100 + seed, 5), *d2_run.build(600, 200 + seed, 5),
                {str(n): d2_run.build(800, 300 + seed + n, n) for n in (5, 11, 21)},
                bce, auc_m)
    if name.startswith("E1-real"):
        mode = "raw" if name.endswith("RAW") else "norm"
        X, yd, _ = REAL[mode]
        (Xtr, ytr), (Xva, yva), (Xte, yte) = split(X, yd, seed)
        return Xtr, ytr, Xva, yva, {"": (Xte, yte)}, bce, auc_m
    if name == "H1b-regr":
        Xtr, ytr = ed2_run.build_H1b(3000, 100 + seed)
        Xva, yva = ed2_run.build_H1b(600, 200 + seed)
        Xte, yte = ed2_run.build_H1b(1000, 300 + seed)
        return wrap(Xtr), ytr, wrap(Xva), yva, {"": (wrap(Xte), yte)}, bce, auc_m
    Xtr, ytr, _ = gen.make(3000, 100 + seed)
    Xva, yva, _ = gen.make(600, 200 + seed)
    Xte, yte, _ = gen.make(1000, 300 + seed)
    return wrap(Xtr), ytr, wrap(Xva), yva, {"": (wrap(Xte), yte)}, bce, auc_m


TASKS = ["R2b-synth", "E1-real-NORM", "E1-real-RAW", "D1b-attr-synth",
         "D2b-varN-synth", "H1b-regr", "NA-regr"]

if __name__ == "__main__":
    print("parsing real telemetry ...", flush=True)
    segs = real_data.parse()
    REAL = {m: real_data.build(segs, 7, m, max_per_class=3374, seed=0)
            for m in ("raw", "norm")}
    for m, (X, yd, _) in REAL.items():
        print("  E1 %s: %s  class balance %.2f" % (m, tuple(X.shape), yd.mean()), flush=True)

    res = json.load(open(OUT)) if os.path.exists(OUT) else {}
    for task in TASKS:
        res.setdefault(task, {})
        for var in VARIANTS:
            if var in res[task] and len(res[task][var].get("runs", [])) >= len(SEEDS):
                print("=== %s / %s (완료, 건너뜀)" % (task, var), flush=True)
                continue
            runs = []
            for sd in SEEDS:
                torch.manual_seed(sd)
                Xtr, ytr, Xva, yva, tests, loss, metric = make_task(task, sd)
                t = time.time()
                net = RelationalScorePredictor(relational=var)
                net, ep = fit(net, Xtr, ytr, Xva, yva, loss, metric)
                sc = {k: round(metric(net, Xe, ye), 4) for k, (Xe, ye) in tests.items()}
                runs.append(sc)
                print("  %-15s %-10s seed=%d ep=%2d  %s  (%.1f min)"
                      % (task, var, sd, ep,
                         " ".join("%s=%.4f" % (k or "score", v) for k, v in sc.items()),
                         (time.time() - t) / 60), flush=True)
            keys = list(runs[0])
            res[task][var] = dict(
                params=count(RelationalScorePredictor(relational=var)),
                runs=runs,
                mean={k: round(float(np.mean([r[k] for r in runs])), 4) for k in keys},
                sd={k: round(float(np.std([r[k] for r in runs])), 4) for k in keys})
            json.dump(res, open(OUT, "w"), indent=1)
            m = res[task][var]["mean"]; s = res[task][var]["sd"]
            print("  -> %-15s %-10s %s" % (task, var,
                  " ".join("%s=%.4f±%.4f" % (k or "score", m[k], s[k]) for k in keys)),
                  flush=True)
    print("done", flush=True)
