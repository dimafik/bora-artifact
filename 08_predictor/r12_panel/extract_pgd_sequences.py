"""Emit the actual evasive delay sequences the white-box attack produced.

panel2.py reports only summary statistics, so the question "does the sequence
that evaded detection still harm the ordering service?" cannot be asked of its
output.  This reruns exactly the winning combination it recorded for each
autocorrelation floor -- same learning rate, seed and initialisation -- and
writes the sequences themselves.

Reproducing rather than re-searching matters: pgd() is deterministic given
(target, rho_min, lr, seed, init), so the sequences written here are the ones
behind the AUC values the manuscript quotes, not a fresh sample that happens to
look similar.  The check at the end asserts the reproduced AUC matches the
recorded one, and only our own detector is rebuilt, which is why this takes a
couple of minutes rather than the 77 the full panel took.

Also writes matched healthy sequences and the two reference conditions the
potency experiment needs: the attack class as the benchmark defines it (AR(1)
at 0.85-0.95) and plain white noise.
"""
import json
import os
import sys

import numpy as np
import torch

sys.path.insert(0, ".")
sys.path.insert(0, "..")
sys.path.insert(0, "../predictor")
import gen
import project
from model import ScorePredictor, CONFIG
from panel2 import Torchable, pgd, N_ATK

OUT = "pgd_sequences.npz"
META = "pgd_sequences.json"


def our_detector():
    tf = ScorePredictor(CONFIG)
    tf.load_state_dict(torch.load("best_mm_r12.pt", map_location="cpu"))
    tf.eval()
    return Torchable("Transformer (ours, retrained)",
                     sum(p.numel() for p in tf.parameters()),
                     lambda X, n=tf: n(X)["anomaly"].squeeze(1))


def main():
    recorded = json.load(open("panel2_results.json", encoding="utf-8"))
    ours = next(e for e in recorded if e["name"].startswith("Transformer"))
    model = our_detector()

    # the same healthy reference panel2 scored against
    rng = np.random.default_rng(999)
    healthy = np.stack([gen._white(rng) for _ in range(N_ATK)]).astype(np.float32)
    h = model.score_np(healthy)

    arrays = {"healthy_white": healthy}
    meta = {"n_per_condition": N_ATK, "window": gen.K,
            "mean": gen.MEAN, "std": gen.STD, "conditions": {}}

    # the attack class as the benchmark defines it, for reference
    rng2 = np.random.default_rng(1234)
    atk_class = np.stack([gen._ar1(rng2, rng2.uniform(0.85, 0.95))
                          for _ in range(N_ATK)]).astype(np.float32)
    arrays["attack_class_ar1"] = atk_class

    for key in ["rho_0.0", "rho_0.3", "rho_0.6", "rho_0.8"]:
        c = ours["sweep"][key]["best_combo"]
        raw, ac, mu, sd, feas = pgd(model, float(key.split("_")[1]),
                                    c["lr"], c["seed"], c["init"])
        a = gen.auc(np.r_[np.zeros(N_ATK), np.ones(N_ATK)],
                    np.r_[h, model.score_np(raw)])
        ok = abs(a - c["auc"]) < 5e-4
        print("  %-9s AUC %.4f (기록 %.4f) %s  autocorr %.3f  mean %.2f  std %.2f"
              % (key, a, c["auc"], "일치" if ok else "!! 불일치", ac, mu, sd))
        assert ok, "%s: reproduced %.4f vs recorded %.4f" % (key, a, c["auc"])
        arrays["pgd_" + key] = raw
        meta["conditions"]["pgd_" + key] = dict(
            rho_min=float(key.split("_")[1]), auc=round(a, 4),
            realised_autocorr=round(ac, 3), mean=round(mu, 3), std=round(sd, 3),
            feasible_frac=round(feas, 3), **{k: c[k] for k in ("lr", "seed", "init")})

    for name, arr in (("healthy_white", healthy), ("attack_class_ar1", atk_class)):
        s = model.score_np(arr)
        meta["conditions"][name] = dict(
            realised_autocorr=round(float(project.autocorr1(torch.tensor(arr)).mean()), 3),
            mean=round(float(arr.mean()), 3),
            std=round(float(arr.std(axis=1).mean()), 3),
            mean_anomaly_score=round(float(s.mean()), 4))

    np.savez_compressed(OUT, **arrays)
    json.dump(meta, open(META, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    print("\nwrote %s (%.1f KB) / %s"
          % (OUT, os.path.getsize(OUT) / 1024, META))
    print("조건 %d개 x %d창 x %d틱" % (len(arrays), N_ATK, gen.K))


if __name__ == "__main__":
    sys.exit(main())
