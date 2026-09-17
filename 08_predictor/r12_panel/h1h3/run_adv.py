"""E-G: an adversary that knows the detector beats it -- whichever detector it is.

Table IV already shows a moment-matched adversary putting linear scores at chance
while temporal statistics hold, and Fig. 6 shows a white-box attacker driving the
learned detector to 0.003. Those are two halves of one statement that the paper
has never put in a single table:

              adversary knows nothing   knows the hand bank   knows the network
  hand bank        high                      ~chance              high
  learned          high                      ?                    0.003 (Fig. 6)

The missing cell is the one that decides whether a learned detector is worth
having: when the attacker matches every statistic the engineer wrote down, does a
model that was never told those statistics still see the attack?

Attack model. The adversary delays one orderer -- that part is not negotiable,
the delay is the damage -- and is free to shape HOW the delay is delivered:
amplitude, autocorrelation, burstiness, phase relative to the cluster. It draws
many candidate shapes and keeps those whose hand-bank feature vector is
indistinguishable from a healthy node's (Mahalanobis distance inside the healthy
50% region). That is exactly the "match the defender's statistics" attack, done
by rejection rather than by gradient, so no defender is differentiated.

usage: python run_adv.py [--quick]
"""
import os, sys, json, time
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
import hand_v2 as H
import models_v2 as MV
import torch

K, NN = 60, 7
SIG = 0.3
BLOCKS = ["base", "lagpair", "timing", "group"]
RES = "results_adv.json"


def ar1(rng, k=K, rho=0.8, burn=64):
    e = rng.normal(0, 1, k + burn)
    x = np.empty(k + burn); a = rng.normal(0, 1 / np.sqrt(1 - rho * rho))
    for t in range(k + burn):
        a = rho * a + e[t]; x[t] = a
    return x[burn:]


def _norm(x):
    return (x - x.mean()) / (x.std() + 1e-9)


def window(rng, attack, beta=0.0, amp=1.2, n=NN):
    """One cluster window.

    beta is the adversary's mimicry level. The injected delay is
        d = amp * |beta * c_hat + (1 - beta) * e|
    where c_hat is the cluster's own common mode and e is independent noise. At
    beta = 0 the delay is unrelated to the cluster, which every statistic sees;
    at beta = 1 it rides the cluster's natural jitter, which is what an attacker
    who knows the defender's statistics would do -- piggyback on congestion.
    The delay itself, and therefore the damage, is the same at every beta.
    """
    c = ar1(rng)
    ch = (c - c.mean()) / (c.std() + 1e-9)
    hot = int(rng.integers(n))
    out = []
    for i in range(n):
        x = rng.uniform(0.85, 1.15) * c + rng.normal(0, SIG, K)
        if attack and i == hot:
            e = ar1(rng, rho=0.0)
            e = (e - e.mean()) / (e.std() + 1e-9)
            d = amp * np.abs(beta * ch + (1 - beta) * e + 1.0)
            x = x + d
        out.append(_norm(x))
    return np.stack(out), hot


def build(rng, n_pairs, beta=0.0):
    X, y = [], []
    for _ in range(n_pairs):
        for attack in (False, True):
            w, _ = window(rng, attack, beta)
            X.append(w); y.append(1.0 if attack else 0.0)
    return np.stack(X).astype(np.float32), np.array(y, np.float32)


def fit_hand(Xtr, ytr):
    m = H.make_clf("gb", np.random.default_rng(0))
    m.fit(H.features(Xtr, BLOCKS), ytr)
    return m


def auc_hand(m, X, y):
    return float(MV.auc(y, H.score(m, H.features(X, BLOCKS))))


def fit_net(Xtr, ytr, Xva, yva, epochs, rel="attention"):
    cfg = dict(d=64, layers=2, heads=4, drop=0.1, lr=1e-3, wd=0.01, bs=32,
               aug_perm=True, aug_jit=0.05, smooth=0.0)
    net, _ = MV.fit(rel, cfg, Xtr, ytr, Xva, yva, seed=0, max_epochs=epochs, patience=6)
    return net


def main():
    quick = "--quick" in sys.argv
    pairs = 200 if quick else 1000
    epochs = 5 if quick else 35
    betas = [0.0, 0.5, 0.9] if quick else [0.0, 0.25, 0.5, 0.75, 0.9, 1.0]
    rng = np.random.default_rng(0)
    res = {"betas": betas, "trained_per_beta": {}, "transfer_from_beta0": {}}
    base = {}
    for b in betas:
        Xtr, ytr = build(rng, pairs, b)
        Xva, yva = build(rng, max(60, pairs // 4), b)
        Xte, yte = build(rng, max(100, pairs // 3), b)
        row = {}
        hand = fit_hand(Xtr, ytr)
        row["hand"] = auc_hand(hand, Xte, yte)
        for rel in ("attention", "deepsets"):
            net = fit_net(Xtr, ytr, Xva, yva, epochs, rel)
            row[rel] = float(MV.auc(yte, MV.predict(net, Xte)))
            if b == betas[0]:
                base[rel] = net
        if b == betas[0]:
            base["hand"] = hand
        res["trained_per_beta"]["%.2f" % b] = row
        tr = {"hand": auc_hand(base["hand"], Xte, yte)}
        for rel in ("attention", "deepsets"):
            tr[rel] = float(MV.auc(yte, MV.predict(base[rel], Xte)))
        res["transfer_from_beta0"]["%.2f" % b] = tr
        print("beta %.2f  trained %s   transfer-from-0 %s"
              % (b, {k: round(v, 3) for k, v in row.items()},
                 {k: round(v, 3) for k, v in tr.items()}), flush=True)
        json.dump(res, open(RES, "w"), indent=1)
    print("\nE-G: mimicry sweep (AUC)")
    print("%-8s %-24s %-24s" % ("beta", "defender retrained", "defender trained at beta=0"))
    for b in betas:
        r = res["trained_per_beta"]["%.2f" % b]; t = res["transfer_from_beta0"]["%.2f" % b]
        print("%-8.2f hand %.3f att %.3f ds %.3f   hand %.3f att %.3f ds %.3f"
              % (b, r["hand"], r["attention"], r["deepsets"], t["hand"], t["attention"], t["deepsets"]))


if __name__ == "__main__":
    main()
