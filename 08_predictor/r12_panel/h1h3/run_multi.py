"""E-F: one model, three outputs, against three rules written separately.

The deployed predictor emits more than a verdict: per-node risk at three horizons
(30/60/90 s), from one forward pass, and the advisor reads the 30 s median. A
threshold rule answers one question only. This asks whether the extra outputs are
worth anything on the real log:

  det   is any orderer degraded in this window            (AUC)
  attr  which one                                         (top-1)
  h30/h60/h90  will THAT node still be degraded 30/60/90 s from the window end
               -- the question the deployed heads are trained on   (AUC)

Baselines get the same three questions, each answered by the rule an engineer
would write: level threshold for det, argmax level for attr, persistence for the
horizons (assume the current state continues, which on a step injection is a
strong baseline and the honest one to beat).

Windows are cut from the raw tick stream (not the constant-hot-set segments), so
transitions are inside the data, and the split is by TIME: the first 70% of the
stream trains, the last 20% tests, with a 10% gap so no window spans the cut.
"""
import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
PANEL = _os.path.dirname(HERE)                 # 08_predictor/r12_panel
PRED = _os.path.dirname(PANEL)                 # 08_predictor
PKG = _os.path.dirname(PRED)                   # artifact_package
import os, sys, json, re, time, pickle
import numpy as np
import torch
import torch.nn as nn

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
import models_v2 as MV

LOG = _os.environ.get("BORA_DAEMON_LOG", "predictor_daemon.log")  # 247 MB, kept on the testbed
CACHE = "ticks_n7.pkl"
TICK = re.compile(r"^(\d+\.\d+) .*scores=(.*)$")
NODE = re.compile(r"o(\d+):[-\d.]+\(rtt(\d+)\)")
HOT_MS, WIN, STRIDE, NN = 50, 60, 10, 7
RES = "results_multi.json"


def ticks():
    """All N=7 ticks in order: (t, rtt[7], hot mask[7])."""
    if os.path.exists(CACHE):
        return pickle.load(open(CACHE, "rb"))
    T, R, H = [], [], []
    with open(LOG, encoding="utf-8", errors="replace") as f:
        for ln in f:
            m = TICK.match(ln)
            if not m:
                continue
            d = NODE.findall(m.group(2))
            if len(d) != NN:
                continue
            r = np.array([float(x) for _, x in d], dtype=np.float32)
            T.append(float(m.group(1))); R.append(r); H.append(r > HOT_MS)
    out = (np.array(T), np.stack(R), np.stack(H))
    pickle.dump(out, open(CACHE, "wb"))
    return out


def build(t, rtt, hot, lo, hi):
    """Windows in [lo,hi) with detection, attribution and horizon labels."""
    X, ydet, yattr, yh = [], [], [], []
    horizons = (30.0, 60.0, 90.0)
    for i in range(lo, hi - WIN, STRIDE):
        w = rtt[i:i + WIN]
        end = i + WIN - 1
        h = hot[end]
        n_hot = int(h.sum())
        z = (w - w.mean(0)) / (w.std(0) + 1e-6)            # NORM regime, per node
        X.append(z.T.astype(np.float32))
        ydet.append(1.0 if n_hot == 1 else 0.0)
        yattr.append(int(np.argmax(h)) if n_hot == 1 else -1)
        row = []
        for H_s in horizons:
            j = np.searchsorted(t, t[end] + H_s)
            row.append(1.0 if (j < len(hot) and n_hot == 1 and hot[j][np.argmax(h)]) else 0.0)
        yh.append(row)
    return (np.stack(X), np.array(ydet, dtype=np.float32),
            np.array(yattr, dtype=np.int64), np.array(yh, dtype=np.float32))


class Multi(nn.Module):
    """One trunk, four heads."""
    def __init__(s, rel="attention", d=64, layers=2, heads=4, drop=0.1):
        super().__init__()
        s.body = MV.Net(rel, d=d, layers=layers, heads=heads, drop=drop)
        s.body.head = nn.Identity()
        s.det = nn.Linear(2 * d, 1)
        s.attr = nn.Linear(2 * d, NN)
        s.hor = nn.Linear(2 * d, 3)

    def forward(s, x):
        f = s.body(x)
        return s.det(f).squeeze(-1), s.attr(f), s.hor(f)


def fit_multi(Xtr, ytr, Xva, yva, epochs=20, patience=5, bs=32, lr=1e-3):
    torch.manual_seed(0)
    net = Multi()
    opt = torch.optim.AdamW(net.parameters(), lr=lr, weight_decay=0.01)
    bce, ce = nn.BCEWithLogitsLoss(), nn.CrossEntropyLoss(ignore_index=-1)
    Xt = torch.tensor(Xtr); dt = torch.tensor(ytr[0]); at = torch.tensor(ytr[1].astype('int64'))
    ht = torch.tensor(ytr[2])
    best, bad, state = -1, 0, None
    for ep in range(epochs):
        net.train()
        perm = torch.randperm(len(Xt))
        for k in range(0, len(Xt) - bs + 1, bs):
            i = perm[k:k + bs]
            opt.zero_grad()
            d, a, h = net(Xt[i])
            loss = bce(d, dt[i]) + ce(a, at[i]) + bce(h, ht[i])
            loss.backward(); nn.utils.clip_grad_norm_(net.parameters(), 1.0); opt.step()
        sc = evaluate_net(net, Xva, yva)
        m = sc["det_auc"] + sc["attr_top1"] + np.mean([sc["h%d_auc" % x] for x in (30, 60, 90)])
        if m > best + 1e-4:
            best, bad = m, 0
            state = {k: v.detach().clone() for k, v in net.state_dict().items()}
        else:
            bad += 1
            if bad >= patience:
                break
    net.load_state_dict(state); net.eval()
    return net


def evaluate_net(net, X, y, bs=128):
    net.eval()
    D, A, Hh = [], [], []
    with torch.no_grad():
        for k in range(0, len(X), bs):
            d, a, h = net(torch.tensor(X[k:k + bs]))
            D.append(d.numpy()); A.append(a.numpy()); Hh.append(h.numpy())
    D, A, Hh = np.concatenate(D), np.concatenate(A), np.concatenate(Hh)
    ydet, yattr, yh = y
    out = {"det_auc": float(MV.auc(ydet, D))}
    m = yattr >= 0
    out["attr_top1"] = float((A[m].argmax(1) == yattr[m]).mean()) if m.any() else float("nan")
    for i, hh in enumerate((30, 60, 90)):
        out["h%d_auc" % hh] = float(MV.auc(yh[:, i], Hh[:, i])) if len(set(yh[:, i])) > 1 else float("nan")
    return out


def rules(Xtr, ytr, Xte, yte):
    """Three separate rules, each the obvious one for its question."""
    def level(X):
        return X.mean(2)                                    # NORM: per-node mean is 0, so
    def spread(X):
        return X.std(2)                                     # use dispersion and lag-1 instead
    def lag1(X):
        z = X - X.mean(2, keepdims=True)
        return (z[:, :, 1:] * z[:, :, :-1]).mean(2) / (X.var(2) + 1e-9)
    def feats(X):
        return np.stack([spread(X), lag1(X)], -1)           # (B,N,2)
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import make_pipeline
    ydet, yattr, yh = ytr
    Ftr = feats(Xtr); Fte = feats(Xte)
    det = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000))
    det.fit(Ftr.reshape(len(Ftr), -1), ydet)
    out = {"det_auc": float(MV.auc(yte[0], det.decision_function(Fte.reshape(len(Fte), -1))))}
    # attribution: the node whose lag-1 autocorrelation is most unlike its peers
    s = -np.abs(lag1(Xte) - np.median(lag1(Xte), 1, keepdims=True))
    m = yte[1] >= 0
    out["attr_top1"] = float((s[m].argmin(1) == yte[1][m]).mean()) if m.any() else float("nan")
    # horizons: persistence -- whatever is true now is predicted to hold
    for i, hh in enumerate((30, 60, 90)):
        pred = yte[0]                                        # "currently one node hot"
        out["h%d_auc" % hh] = float(MV.auc(yte[2][:, i], pred)) if len(set(yte[2][:, i])) > 1 else float("nan")
    return out


def label_runs(t, rtt, hot):
    """All windows once, tagged with the contiguous run of constant label they
    come from. The log is 84% "exactly one node hot" and the other class sits in
    a few stretches, so a plain time cut puts one class entirely on one side.
    Splitting RUNS of each label keeps both classes on both sides and still never
    shares a stretch between train and test."""
    X, yd, ya, yh, run_id = [], [], [], [], []
    horizons = (30.0, 60.0, 90.0)
    n = len(t)
    cur, rid = None, -1
    for i in range(0, n - WIN, STRIDE):
        end = i + WIN - 1
        h = hot[end]
        n_hot = int(h.sum())
        key = (n_hot == 1, int(np.argmax(h)) if n_hot == 1 else -1)
        if key != cur:
            cur, rid = key, rid + 1
        w = rtt[i:i + WIN]
        z = (w - w.mean(0)) / (w.std(0) + 1e-6)
        X.append(z.T.astype(np.float32))
        yd.append(1.0 if n_hot == 1 else 0.0)
        ya.append(key[1])
        row = []
        for H_s in horizons:
            j = np.searchsorted(t, t[end] + H_s)
            row.append(1.0 if (j < len(hot) and n_hot == 1 and hot[j][key[1]]) else 0.0)
        yh.append(row)
        run_id.append(rid)
    return (np.stack(X), np.array(yd, np.float32), np.array(ya, np.int64),
            np.array(yh, np.float32), np.array(run_id))


def split_runs(data, seed=0):
    X, yd, ya, yh, rid = data
    rng = np.random.default_rng(seed)
    parts = {"train": [], "val": [], "test": []}
    for lab in (0.0, 1.0):
        runs = sorted({int(r) for r in rid[yd == lab]})
        rng.shuffle(runs)
        n = len(runs)
        n_te = max(1, n // 5)
        parts["test"] += runs[:n_te]
        parts["val"] += runs[n_te:n_te + max(1, n // 10)]
        parts["train"] += runs[n_te + max(1, n // 10):]
    out = {}
    for role, rs in parts.items():
        m = np.isin(rid, rs)
        out[role] = (X[m], yd[m], ya[m], yh[m])
        print("  %-5s windows %6d  one-hot %.2f  h30+ %.2f  runs %d"
              % (role, m.sum(), yd[m].mean(), yh[m][:, 0].mean(), len(rs)), flush=True)
    return out["train"], out["val"], out["test"]


def main():
    t, rtt, hot = ticks()
    n = len(t)
    print("N=7 ticks: %d" % n, flush=True)
    tr, va, te = split_runs(label_runs(t, rtt, hot))
    if len(tr[0]) > 14000:                       # keep the fit to a sane size
        idx = np.random.default_rng(0).choice(len(tr[0]), 14000, replace=False)
        tr = tuple(a[idx] for a in tr)

    res = {}
    t0 = time.time()
    net = fit_multi(tr[0], (tr[1], tr[2], tr[3]), va[0], (va[1], va[2], va[3]))
    res["multi_head_attention"] = evaluate_net(net, te[0], (te[1], te[2], te[3]))
    res["multi_head_attention"]["train_min"] = round((time.time() - t0) / 60, 1)
    res["separate_rules"] = rules(tr[0], (tr[1], tr[2], tr[3]), te[0], (te[1], te[2], te[3]))
    print(json.dumps(res, indent=1))
    json.dump(res, open(RES, "w"), indent=1)


if __name__ == "__main__":
    main()
