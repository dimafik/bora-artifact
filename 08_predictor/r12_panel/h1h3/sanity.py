import numpy as np, torch, time
import rel_gen as G, rel_models as M
from run_h import net_auc, hand_auc
for fam in G.FAMILIES:
    Xtr, ytr = G.build(600, 100, [fam], 5); Xva, yva = G.build(200, 200, [fam], 5)
    Xte, yte = G.build(300, 300, [fam], 5)
    pn = net_auc("per-node", Xtr, ytr, Xva, yva, {"t": (Xte, yte)}, 0, 1e-3)["t"]
    at = net_auc("attention", Xtr, ytr, Xva, yva, {"t": (Xte, yte)}, 0, 1e-3)["t"]
    hf = hand_auc(Xtr, ytr, Xte, yte, [fam])
    print("%-10s per-node %.3f  attention %.3f  hand(own group) %.3f" % (fam, pn, at, hf), flush=True)
