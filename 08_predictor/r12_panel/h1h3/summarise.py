import json, numpy as np
d = json.load(open("results.json"))
MODELS = ["per-node", "hand-fold", "hand-full", "deepsets", "gru-nodes", "relation", "attention"]
def m(task, cond, mod):
    v = d[task].get(cond, {}).get(mod)
    if not v: return None
    a = np.array(list(v.values()), float)
    return a.mean(), (a.std(ddof=1) if len(a) > 1 else 0.0)
for task in ("H1", "H2", "H3"):
    print("\n===", task)
    print("%-12s" % "cond" + "".join("%-16s" % x for x in MODELS))
    for cond in d[task]:
        row = "%-12s" % cond
        for mod in MODELS:
            r = m(task, cond, mod)
            row += "%-16s" % ("-" if r is None else "%.3f±%.3f" % r)
        print(row)
    # decision per condition
    print("-- decision (threshold 0.03)")
    for cond in d[task]:
        att = m(task, cond, "attention")[0]
        others = {k: m(task, cond, k)[0] for k in ("deepsets", "gru-nodes", "relation") if m(task, cond, k)}
        best_non_att = max(others.values())
        hf = m(task, cond, "hand-fold")[0]
        rel = others.get("relation")
        if att >= best_non_att + 0.03 and att >= hf + 0.03:
            verd = "attention advantage"
        elif rel is not None and abs(att - rel) <= 0.03 and min(att, rel) >= hf + 0.03:
            verd = "learned relational operator needed"
        elif hf >= max(att, best_non_att) - 0.03:
            verd = "hand bank suffices"
        else:
            verd = "mixed"
        print("  %-12s att %.3f | best non-att %.3f (%s) | hand-fold %.3f -> %s" %
              (cond, att, best_non_att, max(others, key=others.get), hf, verd))
