"""E-C: what the envelope allows a *wrong* advisor to do, on the real elections.

H1 produced a detector that inverts on an unseen attack family (AUC 0.29). The
question a reviewer will ask is what such a detector costs the cluster. The answer
is not an argument, it is arithmetic on the contract, and the contract's inputs
(N, f, r, cap) were logged at every real election. For each one we replace the
advice actually emitted with the worst advice the contract permits -- the cap
filled entirely with healthy orderers -- and count what is left.

    eligible E_t   = N - |B_t|            (blacklisted nodes stand down)
    ALR            the incumbent is exempt, so a wrong advisor cannot demote it
    majority need  ceil((N+1)/2)          (Proposition 1's condition)

usage: python run_worst.py
"""
import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
PANEL = _os.path.dirname(HERE)                 # 08_predictor/r12_panel
PRED = _os.path.dirname(PANEL)                 # 08_predictor
PKG = _os.path.dirname(PRED)                   # artifact_package
import os, csv, glob, json
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
ROOTS = [_os.environ.get("BORA_RESULTS", "results")]
OUT = "results_worst.json"


def rows():
    for root in ROOTS:
        for p in glob.glob(os.path.join(root, "x1_*", "elections.csv")):
            run = os.path.basename(os.path.dirname(p))
            with open(p) as f:
                for r in csv.DictReader(f):
                    if "cap" not in r or not r.get("N"):
                        continue
                    yield run, r


def main():
    per_run, allrows = {}, []
    for run, r in rows():
        try:
            N, f = int(r["N"]), int(r["f"])
            cap = int(r["cap"]) if r["cap"] not in ("", "NA") else None
            rr = int(r["r"]) if r["r"] not in ("", "NA") else None
            size = int(r["size"]) if r.get("size") not in ("", "NA", None) else 0
        except (ValueError, KeyError):
            continue
        if cap is None or rr is None:
            continue
        worst = min(cap, N)                      # a wrong advisor fills the cap
        eligible = N - worst - rr                # blacklisted stand down, downed are gone
        need = (N + 1 + 1) // 2                  # ceil((N+1)/2)
        allrows.append(dict(run=run, N=N, f=f, r=rr, cap=cap, size=size,
                            worst_blacklist=worst, worst_eligible=eligible,
                            majority_need=need, holds=eligible >= need,
                            live=r.get("live")))
    if not allrows:
        print("no election rows found"); return
    A = allrows
    byN = {}
    for a in A:
        d = byN.setdefault(a["N"], dict(n=0, holds=0, min_elig=99, caps=set(), max_size=0))
        d["n"] += 1
        d["holds"] += int(a["holds"])
        d["min_elig"] = min(d["min_elig"], a["worst_eligible"])
        d["caps"].add(a["cap"])
        d["max_size"] = max(d["max_size"], a["size"])
    print("elections read: %d over %d runs" % (len(A), len({a['run'] for a in A})))
    print("%-4s %-8s %-10s %-22s %-12s %s" % ("N", "count", "caps seen", "worst-case |E_t| (min)", "needs", "holds"))
    for N in sorted(byN):
        d = byN[N]
        print("%-4d %-8d %-10s %-22d %-12d %d/%d" %
              (N, d["n"], sorted(d["caps"]), d["min_elig"], (N + 2) // 2, d["holds"], d["n"]))
    tot_hold = sum(a["holds"] for a in A)
    print("\nworst-case majority survives in %d of %d elections (%.1f%%)" %
          (tot_hold, len(A), 100.0 * tot_hold / len(A)))
    print("largest blacklist actually emitted: %d; largest the cap would allow: %d" %
          (max(a["size"] for a in A), max(a["worst_blacklist"] for a in A)))
    json.dump(dict(elections=len(A), holds=tot_hold,
                   byN={str(k): dict(n=v["n"], holds=v["holds"], min_eligible=v["min_elig"],
                                     caps=sorted(v["caps"]), max_emitted=v["max_size"])
                        for k, v in byN.items()}), open(OUT, "w"), indent=1)
    print("written", OUT)


if __name__ == "__main__":
    main()
