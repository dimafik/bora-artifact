"""E-B: the advisor is swappable — measured on the real five-host feeds.

The paper's guarantee does not depend on which detector fills B_t. Two advisors
have been measured in the closed loop already (the Transformer over 720 forced
elections, a zero-parameter mean-RTT threshold over 480). This scores two cheap
advisors offline on the same cross-host feeds the Transformer was scored on, with
the same onset rule, the same detection rule and the same false-positive rule, so
the three can be put in one table.

  A0  Transformer, theta = 0.65 transplanted   (from scores2.json, for reference)
  A1  trailing-10 median > k x the cluster median            (level rule)
  A2  trailing-10 median deviates > k MADs from the peers    (relational rule)

usage: python run_swap.py
"""
import os as _os
HERE = _os.path.dirname(_os.path.abspath(__file__))
PANEL = _os.path.dirname(HERE)                 # 08_predictor/r12_panel
PRED = _os.path.dirname(PANEL)                 # 08_predictor
PKG = _os.path.dirname(PRED)                   # artifact_package
import os, sys, json, glob
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)
FEEDS = _os.path.join(PKG, "01_testbed_harness", "alg1", "xhost_detect_2026-09-13")
TARGET = 2                       # orderer 3 is column index 2 in feed.csv
TRAIL = 10                       # the paper's trailing-median window


def load(seed):
    a = np.loadtxt(os.path.join(FEEDS, seed, "feed.csv"), delimiter=",")
    return a[:, 0], a[:, 1:]


def trailing_median(x, w=TRAIL):
    out = np.full(len(x), np.nan)
    for i in range(len(x)):
        lo = max(0, i - w + 1)
        out[i] = np.median(x[lo:i + 1])
    return out


def onset_tick(rtt, target=TARGET, rule="raw"):
    """Two onset definitions, because one of them is circular for A1/A2.

    'trailing' is the rule the paper used to score the Transformer: the first
    tick whose trailing 10-tick median exceeds 10x the node's clean median. A1
    and A2 threshold almost that same statistic, so scoring them against it
    would hand them a latency of zero by construction.

    'raw' uses the instantaneous RTT: the first tick whose own value exceeds 10x
    the clean median. It is independent of every trailing statistic and is the
    earliest tick at which any detector could see the injection.
    """
    clean = np.median(rtt[:len(rtt) // 4, target])
    x = trailing_median(rtt[:, target]) if rule == "trailing" else rtt[:, target]
    hit = np.where(x > 10 * clean)[0]
    return int(hit[0]) if len(hit) else None


def advisor_level(rtt, k=3.0):
    """A1: node's trailing median above k x the cluster's own median."""
    tm = np.stack([trailing_median(rtt[:, j]) for j in range(rtt.shape[1])], 1)
    cluster = np.median(tm, 1, keepdims=True)
    return tm > k * cluster


def advisor_rel(rtt, k=6.0):
    """A2: node's trailing median more than k MADs from its peers'."""
    tm = np.stack([trailing_median(rtt[:, j]) for j in range(rtt.shape[1])], 1)
    med = np.median(tm, 1, keepdims=True)
    mad = np.median(np.abs(tm - med), 1, keepdims=True) + 1e-9
    return (tm - med) / mad > k


def evaluate(flag, onset, target=TARGET, ticks_per_s=None, t=None):
    """Same three quantities the paper reports for the Transformer."""
    att = flag[onset:]
    held = int(att[:, target].sum())
    first = np.where(att[:, target])[0]
    lat = None
    if len(first):
        lat = float(t[onset + first[0]] - t[onset]) if t is not None else float(first[0])
    others = [j for j in range(flag.shape[1]) if j != target]
    fp = int(att[:, others].sum())
    return dict(detect_s=lat, held=held, attack_cycles=int(len(att)),
                fp=fp, fp_windows=int(len(att) * len(others)))


def main():
    ref = json.load(open(os.path.join(FEEDS, "scores2.json")))
    tx, onsets = {}, {}
    for e in ref:
        if e["Tc_ms"] == 100 and not e["standardised"]:
            b = e["transplant"]
            tx[e["feed"]] = dict(detect_s=b["detection_latency_s"], held=b["held_cycles"],
                                 attack_cycles=b["attack_cycles"], fp=b["fp_total"],
                                 fp_windows=b["fp_windows"])
            onsets[e["feed"]] = int(e["onset_tick"])
    out = {}
    for seed in ("seed1", "seed2", "seed3"):
        t, rtt = load(seed)
        # the onset the Transformer itself was scored against, so all three
        # advisors are measured from the same instant
        on = onsets[seed]
        row = {"A0_transformer": tx.get(seed), "onset_tick": on,
               "onset_note": "from scores2.json; A1/A2 threshold a statistic close "
                             "to the onset rule, so their latency is optimistic",
               "ticks": int(len(t))}
        row["A1_level_k3"] = evaluate(advisor_level(rtt, 3.0), on, t=t)
        row["A2_relational_k6"] = evaluate(advisor_rel(rtt, 6.0), on, t=t)
        out[seed] = row
        print(seed, "onset", on, flush=True)
        for k in ("A0_transformer", "A1_level_k3", "A2_relational_k6"):
            v = row[k]
            if v:
                print("   %-18s detect %s s  held %s/%s  fp %s/%s" %
                      (k, v["detect_s"], v["held"], v["attack_cycles"], v["fp"], v["fp_windows"]))
    json.dump(out, open("results_swap.json", "w"), indent=1)
    print("written results_swap.json")


if __name__ == "__main__":
    main()
