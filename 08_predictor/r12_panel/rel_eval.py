"""Does adding the node-axis attention to the deployed encoder actually pay?

Control and treatment differ in exactly one thing: relational=False is the
deployed architecture (each node encoded and scored alone), relational=True adds
one attention layer over the node axis before temporal pooling.  Same encoder,
same training budget, same data, same early stopping.

Five benchmarks, and the last two are regression checks.  A relational layer that
helps on multi-node tasks but degrades single-node detection would be useless in
deployment, so those are reported whichever way they come out.

    R2b   one node slow vs all nodes slow          (detection, AUC)
    D1b   which node is the degraded one           (attribution, top-1)
    D2b   train at N=5, test at N=5..21            (transfer, AUC)
    H1b   short attack segment, single node        (regression, AUC)
    NA    non-adaptive moment-matched, single node (regression, AUC)
"""
import sys, json, time, copy
import numpy as np
import torch
import torch.nn as nn

sys.path.insert(0, "."); sys.path.insert(0, ".."); sys.path.insert(0, "../predictor")
import gen, hard_gen, ed_run as E
import r2_run, d1_run, d2_run, ed2_run
from relational import RelationalScorePredictor, count

LRS = [3e-4, 1e-3]


def fit(net, Xtr, ytr, Xva, yva, lr, loss, metric, epochs=25, patience=5, bs=32):
    opt = torch.optim.Adam(net.parameters(), lr=lr)
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


def multi_scores(net, X, bs=32):
    """window-level score = max over nodes (a set is anomalous if a member is)."""
    net.eval(); out = []
    with torch.no_grad():
        for i in range(0, len(X), bs):
            out.append(net(X[i:i + bs]).max(1).values)
    return torch.cat(out).numpy()


def auc_multi(net, X, y):
    return gen.auc(y.numpy(), multi_scores(net, X))


def top1(net, X, y, bs=64):
    net.eval(); ok = 0
    with torch.no_grad():
        for i in range(0, len(X), bs):
            ok += (net(X[i:i + bs]).argmax(1) == y[i:i + bs]).sum().item()
    return ok / len(X)


def single_wrap(X):
    """single-node benchmark -> (B, 1, K, 8) so the same model can run on it."""
    return X.unsqueeze(1)


def main():
    res = {}
    bce = lambda o, t: nn.functional.binary_cross_entropy_with_logits(o.max(1).values, t)
    ce = lambda o, t: nn.functional.cross_entropy(o, t)

    tasks = []

    Xtr, ytr = r2_run.build(2500, 101); Xva, yva = r2_run.build(600, 202)
    Xte, yte = r2_run.build(1200, 303)
    tasks.append(("R2b", Xtr, ytr, Xva, yva, {"": (Xte, yte)}, bce, auc_multi))

    Xtr, ytr = d1_run.build(6000, 101); Xva, yva = d1_run.build(1000, 202)
    Xte, yte = d1_run.build(2000, 303)
    tasks.append(("D1b", Xtr, ytr, Xva, yva, {"": (Xte, yte)}, ce, top1))

    Xtr, ytr = d2_run.build(4000, 101, 5); Xva, yva = d2_run.build(800, 202, 5)
    tests = {str(n): d2_run.build(1200, 300 + n, n) for n in [5, 7, 9, 11, 21]}
    tasks.append(("D2b", Xtr, ytr, Xva, yva, tests, bce, auc_multi))

    Xtr, ytr = ed2_run.build_H1b(6000, 101); Xva, yva = ed2_run.build_H1b(800, 202)
    Xte, yte = ed2_run.build_H1b(1500, 303)
    tasks.append(("H1b", single_wrap(Xtr), ytr, single_wrap(Xva), yva,
                  {"": (single_wrap(Xte), yte)}, bce, auc_multi))

    Xtr, ytr, _ = gen.make(6000, 101); Xva, yva, _ = gen.make(800, 202)
    Xte, yte, _ = gen.make(1500, 303)
    tasks.append(("NA", single_wrap(Xtr), ytr, single_wrap(Xva), yva,
                  {"": (single_wrap(Xte), yte)}, bce, auc_multi))

    for name, Xtr, ytr, Xva, yva, tests, loss, metric in tasks:
        print("=== %s" % name, flush=True)
        res[name] = {}
        for rel in (False, True):
            best = None
            for lr in LRS:
                t = time.time()
                net = RelationalScorePredictor(relational=rel)
                net, ep = fit(net, Xtr, ytr, Xva, yva, lr, loss, metric)
                sc = {k: round(metric(net, Xe, ye), 4) for k, (Xe, ye) in tests.items()}
                key = list(tests)[0]
                print("  rel=%-5s lr=%.0e ep=%2d  %s  (%.1f min)"
                      % (rel, lr, ep, " ".join("%s=%.4f" % (k or "score", v)
                                               for k, v in sc.items()),
                         (time.time() - t) / 60), flush=True)
                if best is None or sc[key] > best["scores"][key]:
                    best = dict(relational=rel, lr=lr, params=count(net), scores=sc)
            res[name]["rel" if rel else "base"] = best
            json.dump(res, open("rel_eval.json", "w"), indent=1)
    print("done", flush=True)


if __name__ == "__main__":
    main()
