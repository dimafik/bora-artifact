"""Cross-evaluation: does an attack tuned against the Transformer also fool the
others?  The manuscript claims evading the learned detector and staying stealthy
against a linear one are "mutually exclusive"; that is a statement about ONE
perturbation scored by BOTH detectors, which the per-model sweep does not test.
"""
import sys, json, numpy as np, torch
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, "."); sys.path.insert(0, ".."); sys.path.insert(0, "../predictor")
import panel2 as P, gen

rows = json.load(open("panel2_results.json", encoding="utf-8"))
best = {r["name"]: r["sweep"]["rho_0.0"]["best_combo"] for r in rows}
Xtr, ytr, _ = gen.make(10000, seed=101)
ms = P.build_models(Xtr, ytr, "best_mm_r12.pt")
by = {m.name: m for m in ms}

rng = np.random.default_rng(999)
healthy = np.stack([gen._white(rng) for _ in range(P.N_ATK)]).astype(np.float32)
lab = np.r_[np.zeros(P.N_ATK), np.ones(P.N_ATK)]

out = {}
for tgt in ["Transformer (ours, retrained)", "logistic / 40 summary stats"]:
    c = best[tgt]
    raw, ac, mu, sd, feas = P.pgd(by[tgt], 0.0, c["lr"], c["seed"], c["init"])
    scored = {n: round(gen.auc(lab, np.r_[m.score_np(healthy), m.score_np(raw)]), 4)
              for n, m in by.items()}
    out[tgt] = dict(combo=c, realised_ac=round(ac, 3), mean=round(mu, 3),
                    std=round(sd, 3), feasible=round(feas, 3), scored_by=scored)
    print("\n[%s 를 겨냥한 공격, rho=0]  ac=%.2f mean=%.2f std=%.2f feasible=%.0f%%"
          % (tgt, ac, mu, sd, 100 * feas))
    for n, a in scored.items():
        print("   %-32s AUC=%.4f" % (n[:32], a))
json.dump(out, open("cross_eval.json", "w"), indent=1)
