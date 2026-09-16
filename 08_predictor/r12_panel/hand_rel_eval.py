"""The hand-built relational reference, on the seeds the neural rows use.

`r2b_run.py` computes a pairwise-correlation reference once, on its own split.
This script runs the same features against the five seeds and test sets of
`final_eval.py`, so the column is comparable with the attention row there:

    task                      attention (final_eval.json)   this script
    R2b  one node vs all      0.8127 +- 0.0334              0.8859 +- 0.0053
    D2b  train N=5, test 21   0.9174 +- 0.0034              0.9421 +- 0.0041

Features: the pairwise correlations of the RTT channel across orderers, reduced
to ten summary statistics (mean, s.d., min, max, three smallest, three largest)
and fed to a logistic regression -- eleven parameters, and size-agnostic, so one
fit is evaluated at N = 5, 11 and 21. Output: hand_rel_eval.json.
"""
import sys, os, json

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
for q in (".", "..", "../predictor"):
    sys.path.insert(0, os.path.abspath(q))
import numpy as np
import gen, r2_run, d2_run
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline


def feat(X):
    r = X[:, :, :, 2].numpy()
    z = (r - r.mean(2, keepdims=True)) / (r.std(2, keepdims=True) + 1e-9)
    C = np.einsum("bik,bjk->bij", z, z) / r.shape[2]
    iu = np.triu_indices(r.shape[1], 1)
    pc = C[:, iu[0], iu[1]]
    return np.c_[pc.mean(1), pc.std(1), pc.min(1), pc.max(1),
                 np.sort(pc, 1)[:, :3], np.sort(pc, 1)[:, -3:]]


def fit(X, y):
    return make_pipeline(StandardScaler(), LogisticRegression(max_iter=5000)).fit(feat(X), y.numpy())


def main():
    out = {"R2b": [], "D2b": {"5": [], "11": [], "21": []}}
    for sd in range(5):
        Xtr, ytr = r2_run.build(1500, 100 + sd)
        Xte, yte = r2_run.build(800, 300 + sd)
        m = fit(Xtr, ytr)
        out["R2b"].append(round(float(gen.auc(yte.numpy(), m.decision_function(feat(Xte)))), 4))
        Xtr, ytr = d2_run.build(2500, 100 + sd, 5)
        m = fit(Xtr, ytr)
        for n in (5, 11, 21):
            Xte, yte = d2_run.build(800, 300 + sd + n, n)
            out["D2b"][str(n)].append(round(float(gen.auc(yte.numpy(), m.decision_function(feat(Xte)))), 4))
        print(sd, out["R2b"][-1], {k: v[-1] for k, v in out["D2b"].items()}, flush=True)
    summ = {"R2b": out["R2b"]}
    summ.update({"D2b_" + n: out["D2b"][n] for n in ("5", "11", "21")})
    for k, v in summ.items():
        print("%-8s mean %.4f  sd %.4f" % (k, np.mean(v), np.std(v, ddof=1)))
    json.dump(out, open("hand_rel_eval.json", "w"), indent=1)


if __name__ == "__main__":
    main()
