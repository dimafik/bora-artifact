import json, os
import numpy as np
def j(p):
    return json.load(open(p)) if os.path.exists(p) else None
def ms(v):
    v = list(v); return (float(np.mean(v)), float(np.std(v, ddof=1)) if len(v) > 1 else 0.0)
out = []
A, B = j("results.json"), j("results_big.json")
for tag, d in (("1st", A), ("2nd", B)):
    for task in ("H1", "H2", "H3"):
        rows = []
        for cond, models in d[task].items():
            hand = ms(models["hand-fold"].values())[0]
            att = ms(models["attention"].values())[0]
            best_other = max(ms(models[m].values())[0] for m in ("deepsets", "gru-nodes", "relation"))
            rows.append((cond, hand, att, best_other))
        out.append((task + " " + tag, rows))
print("== H1-H3")
for name, rows in out:
    for cond, hand, att, bo in rows:
        print("%-8s %-12s hand %.3f  attention %.3f  best other net %.3f" % (name, cond, hand, att, bo))
for t in ("T1", "T2"):
    d = j("results_%s.json" % t)
    if d:
        print("\n== %s (confirm, 3 seeds)" % t)
        for fam, c in d["confirm"].items():
            print("  %-10s %.3f +- %.3f" % (fam, np.mean(c), np.std(c, ddof=1) if len(c) > 1 else 0))
d = j("results_real.json")
print("\n== E-A real attribution (top-1, chance 0.143)")
for mode in ("raw", "norm"):
    ks = [k for k in d if k.startswith(mode)]
    for m in ("hand", "per-node", "deepsets", "relation", "attention"):
        v = [d[k][m] for k in ks if d[k].get(m) is not None]
        if v: print("  %-5s %-10s %.3f +- %.3f" % (mode, m, np.mean(v), np.std(v, ddof=1)))
d = j("results_swap.json")
print("\n== E-B advisor swap (real feeds)")
for seed, r in d.items():
    for k in ("A0_transformer", "A1_level_k3", "A2_relational_k6"):
        v = r[k]
        print("  %-6s %-18s detect %.2f s  held %d/%d  fp %d/%d" %
              (seed, k, v["detect_s"], v["held"], v["attack_cycles"], v["fp"], v["fp_windows"]))
d = j("results_worst.json")
print("\n== E-C worst-case advisor: %d of %d elections keep a majority" % (d["holds"], d["elections"]))
d = j("results_cost.json")
print("\n== E-D cost")
for k, v in d.items():
    if "infer_ms" in v: print("  %-22s params %-8s infer %.3f ms" % (k, v.get("params"), v["infer_ms"]))
d = j("results_transfer.json")
print("\n== E-E train N=7 -> test N=9 (top-1, chance 0.111)")
for mode in ("raw", "norm"):
    ks = [k for k in d if k.startswith(mode)]
    for m in ("hand", "per-node", "deepsets", "relation", "attention"):
        v = [d[k][m] for k in ks if d[k].get(m) is not None]
        if v: print("  %-5s %-10s %.3f +- %.3f" % (mode, m, np.mean(v), np.std(v, ddof=1)))
d = j("results_adv2.json")
print("\n== E-G mimicry sweep (3 seeds)")
for b in (0.5, 0.6, 0.75, 0.8, 0.9, 1.0):
    ks = [k for k in d if k.startswith("%.2f/" % b)]
    r = {m: ms([d[k][m] for k in ks]) for m in ("hand", "attention", "deepsets")}
    print("  beta %.2f  hand %.3f+-%.3f  attention %.3f+-%.3f  deepsets %.3f+-%.3f" %
          (b, r["hand"][0], r["hand"][1], r["attention"][0], r["attention"][1],
           r["deepsets"][0], r["deepsets"][1]))
