"""Turn the evasive PGD sequences into netem delay tracks for the testbed.

The question this feeds is the one the panel never asked: a sequence that evaded
the detector still has to *do* something to the ordering service, and nothing in
panel2_results.json says whether it does.  Here each condition becomes a
per-orderer delay track that mm-style replay can drive.

Two things are deliberate.

Every orderer is driven from the same marginal, not just the target.  The
adversary being modelled is moment-matched: its mean and variance equal the
healthy nodes'.  Elevating only orderer3 would make it detectable by mean alone
and would no longer be the attack whose evasion we measured.

Both magnitudes are emitted.  At the benchmark's own 8 ms the attack may be too
small to move throughput at all, which would say the attack class is inert
rather than that autocorrelation is harmless -- a different conclusion.  Scaling
multiplicatively to a 500 ms mean keeps the coefficient of variation and the
autocorrelation of the original, so it is the same attack at an operationally
significant magnitude rather than a new one.
"""
import json
import os
import sys

import numpy as np

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
OUTDIR = r"D:\fabric-d2\results\potency"

N_ORD = 7            # orderer.example.com + orderer2..7
TARGET = 3           # orderer3 is the targeted node throughout the paper
TICKS = 2400         # 0.15 s per tick -> ~6 min, longer than one election phase
CLIP_LO, CLIP_HI = 0.5, 3000.0


def load_conditions():
    z = np.load(os.path.join(HERE, "pgd_sequences.npz"))
    meta = json.load(open(os.path.join(HERE, "pgd_sequences.json"), encoding="utf-8"))
    order = ["healthy_white", "pgd_rho_0.0", "pgd_rho_0.3",
             "pgd_rho_0.6", "pgd_rho_0.8", "attack_class_ar1"]
    return [(k, z[k], meta["conditions"][k]) for k in order], meta


def stitch(windows, ticks, rng):
    """Concatenate whole windows until `ticks` long.

    Windows are taken in a random order and never sliced, so the lag-1
    autocorrelation inside a window is preserved exactly; only the joins between
    windows are uncorrelated, which is also true of the original 60-tick
    telemetry the daemon sees.
    """
    idx = rng.permutation(len(windows))
    out, i = [], 0
    while sum(len(w) for w in out) < ticks:
        out.append(windows[idx[i % len(idx)]])
        i += 1
    return np.concatenate(out)[:ticks]


def autocorr1(x):
    z = (x - x.mean()) / (x.std() + 1e-9)
    return float((z[:-1] * z[1:]).mean())


def main():
    os.makedirs(OUTDIR, exist_ok=True)
    conds, meta = load_conditions()
    rng = np.random.default_rng(20260821)
    base_mean, base_std = meta["mean"], meta["std"]

    index = {"ticks": TICKS, "n_orderers": N_ORD, "target": TARGET,
             "tick_seconds": 0.15, "base_mean_ms": base_mean,
             "base_std_ms": base_std, "tracks": {}}

    healthy_pool = np.load(os.path.join(HERE, "pgd_sequences.npz"))["healthy_white"]

    for scale_name, target_mean in (("m8", 8.0), ("m500", 500.0)):
        k = target_mean / base_mean          # multiplicative: CV and autocorr kept
        for cname, windows, cmeta in conds:
            tgt = stitch(windows, TICKS, np.random.default_rng(rng.integers(1 << 30))) * k
            cols = []
            for o in range(1, N_ORD + 1):
                if o == TARGET:
                    cols.append(tgt)
                else:
                    cols.append(stitch(healthy_pool, TICKS,
                                       np.random.default_rng(rng.integers(1 << 30))) * k)
            M = np.clip(np.stack(cols, axis=1), CLIP_LO, CLIP_HI)

            fn = "%s_%s.csv" % (scale_name, cname)
            np.savetxt(os.path.join(OUTDIR, fn), M, fmt="%.3f", delimiter=",")

            others = np.delete(M, TARGET - 1, axis=1)
            index["tracks"][fn] = dict(
                condition=cname, scale=scale_name, target_mean_ms=target_mean,
                target_realised=dict(
                    mean=round(float(M[:, TARGET - 1].mean()), 2),
                    std=round(float(M[:, TARGET - 1].std()), 2),
                    autocorr=round(autocorr1(M[:, TARGET - 1]), 3)),
                others_realised=dict(
                    mean=round(float(others.mean()), 2),
                    std=round(float(others.std()), 2),
                    autocorr=round(float(np.mean([autocorr1(others[:, j])
                                                  for j in range(others.shape[1])])), 3)),
                detector_auc=cmeta.get("auc"))

    json.dump(index, open(os.path.join(OUTDIR, "index.json"), "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)

    print("%-28s %-8s %-26s %s" % ("track", "AUC", "target mean/std/ac", "others mean/std/ac"))
    print("-" * 96)
    for fn, t in index["tracks"].items():
        a = t["detector_auc"]
        print("%-28s %-8s %6.1f /%6.1f /%6.3f   %6.1f /%6.1f /%6.3f"
              % (fn, "-" if a is None else "%.3f" % a,
                 t["target_realised"]["mean"], t["target_realised"]["std"],
                 t["target_realised"]["autocorr"],
                 t["others_realised"]["mean"], t["others_realised"]["std"],
                 t["others_realised"]["autocorr"]))
    print("\n%d tracks -> %s" % (len(index["tracks"]), OUTDIR))


if __name__ == "__main__":
    sys.exit(main())
