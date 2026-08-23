"""E-A: retrain the Transformer detector on enough data to be a fair comparison.

mm_train.py trained 141,067 parameters on 800 windows.  The data is synthetic, so
that was a choice, not a constraint.  Here: 20,000 training windows, a held-out
validation split for early stopping, and a separate test split for the reported
number.  Architecture, task, representation and marginals are unchanged, so the
only difference from the published 0.903 is how much data the model saw.

Settings are fixed once, per the pre-registration.  If they are changed, the
change and its reason go in the log.
"""
import sys, time, json, copy
import numpy as np
import torch
import torch.nn as nn

sys.path.insert(0, ".")
sys.path.insert(0, "..")
sys.path.insert(0, "../predictor")
import gen
from model import ScorePredictor, CONFIG

TRAIN_PAIRS, VAL_PAIRS, TEST_PAIRS = 10000, 1000, 2000
EPOCHS, BATCH, LR, PATIENCE = 60, 128, 3e-4, 8

t0 = time.time()
Xtr, ytr, _ = gen.make(TRAIN_PAIRS, seed=101)
Xva, yva, _ = gen.make(VAL_PAIRS,  seed=202)
Xte, yte, _ = gen.make(TEST_PAIRS, seed=303)
print("data: train %d / val %d / test %d windows  (%.1fs)"
      % (len(Xtr), len(Xva), len(Xte), time.time() - t0), flush=True)

m = ScorePredictor(CONFIG)
sd = torch.load("../model_small/best.pt", map_location="cpu")
st = sd.get("model_state_dict", sd.get("state_dict", sd)) if isinstance(sd, dict) else sd
m.load_state_dict(st)                       # same warm start as mm_train.py
print("params:", sum(p.numel() for p in m.parameters()), flush=True)

opt = torch.optim.Adam(m.parameters(), lr=LR)
bce = nn.BCEWithLogitsLoss()


def score(model, X):
    model.eval()
    out = []
    with torch.no_grad():
        for i in range(0, len(X), 512):
            out.append(model(X[i:i + 512])["anomaly"].squeeze(1))
    return torch.cat(out).numpy()


best_auc, best_state, bad = -1.0, None, 0
for ep in range(EPOCHS):
    te = time.time()
    m.train()
    perm = torch.randperm(len(Xtr))
    for i in range(0, len(Xtr), BATCH):
        idx = perm[i:i + BATCH]
        opt.zero_grad()
        loss = bce(m(Xtr[idx])["anomaly"].squeeze(1), ytr[idx])
        loss.backward()
        opt.step()
    va = gen.auc(yva.numpy(), score(m, Xva))
    print("epoch %2d  val AUC=%.4f  (%.0fs)" % (ep + 1, va, time.time() - te), flush=True)
    if va > best_auc + 1e-4:
        best_auc, best_state, bad = va, copy.deepcopy(m.state_dict()), 0
    else:
        bad += 1
        if bad >= PATIENCE:
            print("early stop at epoch %d" % (ep + 1), flush=True)
            break

m.load_state_dict(best_state)
test_auc = gen.auc(yte.numpy(), score(m, Xte))
torch.save(best_state, "best_mm_r12.pt")
json.dump({"train_windows": len(Xtr), "val_windows": len(Xva), "test_windows": len(Xte),
           "epochs_run": ep + 1, "best_val_auc": round(best_auc, 4),
           "test_auc": round(test_auc, 4), "params": sum(p.numel() for p in m.parameters()),
           "published_auc_800_windows": 0.903, "minutes": round((time.time() - t0) / 60, 1)},
          open("retrain_result.json", "w"), indent=1)
print("FINAL test AUC=%.4f  (published on 800 windows: 0.903)" % test_auc, flush=True)
print("saved best_mm_r12.pt", flush=True)
