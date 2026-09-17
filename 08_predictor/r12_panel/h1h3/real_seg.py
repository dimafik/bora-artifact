"""E-A: the same relational question, on the real daemon log, split by SEGMENT.

The withdrawn version cut overlapping windows and split them at random, so test
windows shared ticks with training windows. Here a whole segment (one bring-up
with one injection state) goes to train, val or test, and windows never cross.
"""
import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
PANEL = _os.path.dirname(HERE)                 # 08_predictor/r12_panel
PRED = _os.path.dirname(PANEL)                 # 08_predictor
PKG = _os.path.dirname(PRED)                   # artifact_package
import os, sys, json, pickle
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
sys.path.insert(0, PANEL)
sys.path.insert(0, PRED)
CACHE = "real_segs.pkl"


def segments():
    if os.path.exists(CACHE):
        return pickle.load(open(CACHE, "rb"))
    import real_data
    segs = real_data.parse()
    segs = [(list(ids), set(hot), arr.astype(np.float32)) for ids, hot, arr in segs]
    pickle.dump(segs, open(CACHE, "wb"))
    return segs


def report(segs):
    from collections import Counter
    c, w = Counter(), Counter()
    for ids, hot, arr in segs:
        k = (len(ids), len(hot))
        c[k] += 1
        w[k] += max(0, (arr.shape[0] - 60) // 20 + 1)
    print("segments (N,#hot):", dict(sorted(c.items())))
    print("windows  (N,#hot):", dict(sorted(w.items())))
    for n in sorted({len(i) for i, _, _ in segs}):
        one = [s for s in segs if len(s[0]) == n and len(s[1]) == 1]
        many = [s for s in segs if len(s[0]) == n and len(s[1]) > 1]
        if one and many:
            print("N=%-3d usable: %d one-hot segments, %d many-hot segments" % (n, len(one), len(many)))


if __name__ == "__main__":
    s = segments()
    print("segments parsed:", len(s))
    report(s)
