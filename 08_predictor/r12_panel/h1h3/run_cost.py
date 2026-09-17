"""E-D: what each advisor costs, on the path the orderer actually waits on.

The daemon scores every 0.5 s and the guard reads advice under a 50 ms deadline,
so the numbers that matter are per-cycle inference, not training throughput. All
three advisors are timed on the same machine, same input shape, CPU only, which
is what the testbed runs.
"""
import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
PANEL = _os.path.dirname(HERE)                 # 08_predictor/r12_panel
PRED = _os.path.dirname(PANEL)                 # 08_predictor
PKG = _os.path.dirname(PRED)                   # artifact_package
import os, sys, time, json
import numpy as np
import torch

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
sys.path.insert(0, PRED)
import hand_v2 as H
import models_v2 as MV

N, K, REPS = 7, 60, 200


def time_it(fn, reps=REPS, warmup=20):
    for _ in range(warmup):
        fn()
    t0 = time.perf_counter()
    for _ in range(reps):
        fn()
    return (time.perf_counter() - t0) / reps * 1000.0        # ms


def main():
    rng = np.random.default_rng(0)
    x = rng.normal(0, 1, (1, N, K)).astype(np.float32)
    out = {}

    # 1. the deployed predictor, as shipped
    try:
        from predictor.model import ScorePredictor, CONFIG
        m = ScorePredictor(CONFIG) if not isinstance(CONFIG, dict) else ScorePredictor(**CONFIG)
        m.eval()
        p = sum(q.numel() for q in m.parameters())
        xi = torch.zeros(1, CONFIG["window"] if isinstance(CONFIG, dict) else 60,
                         CONFIG["channels"] if isinstance(CONFIG, dict) else 8)
        with torch.no_grad():
            ms = time_it(lambda: m(xi))
        out["deployed_transformer"] = dict(params=int(p), infer_ms=round(ms, 3))
    except Exception as e:                                   # shape/API drift
        out["deployed_transformer"] = dict(error=str(e)[:120])

    # 2. the axial-attention model this study tuned
    cfg = dict(d=64, layers=2, heads=4, drop=0.1, lr=1e-3, wd=0.01, bs=32,
               aug_perm=True, aug_jit=0.05, smooth=0.0)
    net = MV.Net("attention", d=cfg["d"], layers=cfg["layers"], heads=cfg["heads"], drop=cfg["drop"])
    net.eval()
    xt = torch.tensor(x)
    with torch.no_grad():
        ms = time_it(lambda: net(xt))
    out["axial_attention"] = dict(params=int(sum(q.numel() for q in net.parameters())),
                                  infer_ms=round(ms, 3))

    # 3. DeepSets, same trunk
    ds = MV.Net("deepsets", d=cfg["d"], layers=cfg["layers"], heads=cfg["heads"], drop=cfg["drop"])
    ds.eval()
    with torch.no_grad():
        ms = time_it(lambda: ds(xt))
    out["deepsets"] = dict(params=int(sum(q.numel() for q in ds.parameters())), infer_ms=round(ms, 3))

    # 4. the hand bank + logistic (fit once, then score)
    Xtr = rng.normal(0, 1, (600, N, K)).astype(np.float32)
    ytr = (rng.random(600) > 0.5).astype(float)
    blocks = ["base", "lagpair", "timing", "group"]
    clf = H.make_clf("logistic", np.random.default_rng(0))
    t0 = time.time()
    clf.fit(H.features(Xtr, blocks), ytr)
    fit_s = time.time() - t0
    ms = time_it(lambda: clf.decision_function(H.features(x, blocks)))
    out["hand_bank_logistic"] = dict(params=int(clf[-1].coef_.size + 1), infer_ms=round(ms, 3),
                                     fit_s=round(fit_s, 2), features=int(clf[-1].coef_.size))

    # 5. the zero-parameter rules of E-B
    def level_rule():
        tm = np.median(x[0], 1)
        return tm > 3 * np.median(tm)
    out["level_rule"] = dict(params=0, infer_ms=round(time_it(level_rule), 4))

    # training cost of one neural fit at the study's budget
    Xs = rng.normal(0, 1, (1200, N, K)).astype(np.float32)
    ys = (rng.random(1200) > 0.5).astype(np.float32)
    t0 = time.time()
    MV.fit("attention", cfg, Xs, ys, Xs[:200], ys[:200], seed=0, max_epochs=3, patience=3)
    out["axial_attention"]["train_s_per_3_epochs"] = round(time.time() - t0, 1)

    print(json.dumps(out, indent=1))
    json.dump(out, open("results_cost.json", "w"), indent=1)
    budget = 50.0
    print("\nguard read deadline %g ms; daemon cycle 500 ms" % budget)
    for k, v in out.items():
        if "infer_ms" in v:
            print("  %-22s %8s params  %7.3f ms  %s" %
                  (k, v.get("params", "-"), v["infer_ms"],
                   "within deadline" if v["infer_ms"] < budget else "OVER deadline"))


if __name__ == "__main__":
    main()
