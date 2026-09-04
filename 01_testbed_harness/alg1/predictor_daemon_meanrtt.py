"""B-20 arm: the same BORA advisor with a zero-parameter detector in it.

This is `predictor_daemon_n.py` with exactly one thing changed -- the function
that turns a telemetry window into a per-orderer score.  The feed reader, the
r derivation, the Algorithm 1 cap |B_t| < f - r, the advice payload, the log
format and the failure handling are all copied verbatim, so a difference in the
outcome is a difference in the detector and not in the envelope around it.

Why a mean-RTT rule and not std(dRTT).  The panel's zero-parameter entry is
std(dRTT), which is the right statistic for the *moment-matched synthetic*
task, where the means are equal by construction and only the variance channels
carry signal.  On this testbed the injected fault is a steady +200 ms egress
delay: it moves the mean from about 0.5 ms to about 200 ms and, being steady,
*lowers* dRTT variance rather than raising it.  Feeding std(dRTT) to the live
feed would measure jitter, not the fault.  The live zero-parameter detector is
a mean-RTT threshold, and that is what this daemon uses.

What this arm can and cannot show.  It can show that the exclusion the paper
reports is a property of the envelope -- the cap, the fail-open counter and the
two guards -- rather than of the model that fills it: the same 0/N result should
follow whether the score comes from a 141k-parameter Transformer or from one
comparison.  It cannot show that a cheap detector handles a moment-matched
adversary; Section V-E already measures that case and finds every linear
functional at chance.  The two statements are about different adversaries and
neither implies the other.

Usage:  python predictor_daemon_meanrtt.py [thresh] [N] [f] [rtt_cut_ms]
        e.g. python predictor_daemon_meanrtt.py 0.65 7 3 50
"""
import sys, os, json, time
import numpy as np

FEED = r"D:\fabric-d2\results\rtt_feed.csv"
BT = r"D:\fabric-d2\results\bt.json"
LOG = r"D:\fabric-d2\results\predictor_daemon_meanrtt.log"

K = 64                # window length, matching CONFIG.window_len
PERIOD = 0.5

THRESH = float(sys.argv[1]) if len(sys.argv) > 1 else 0.65   # score below -> risky
N = int(sys.argv[2]) if len(sys.argv) > 2 else 5
F = int(sys.argv[3]) if len(sys.argv) > 3 else (N - 1) // 2
# The one calibrated constant.  Healthy orderers sit near 0.5 ms on this
# testbed and the injected target near 200 ms, so any cut well inside that gap
# gives the same decision; 50 ms is two orders of magnitude from both ends.
RTT_CUT = float(sys.argv[4]) if len(sys.argv) > 4 else 50.0

# --- r detection, copied verbatim from predictor_daemon_n.py -----------------
RTT_FAIL = 1500.0
UNRESP_MS = 1000.0
UNRESP_W = 6
UNRESP_FRAC = 0.5

# The scores are written on the same scale the Transformer daemon emits, so the
# 0.65 threshold, the log format and every downstream reader are unchanged.
SCORE_HEALTHY = 0.85
SCORE_RISKY = 0.42


def read_rows():
    try:
        rows = [l.strip().split(",") for l in open(FEED).read().splitlines() if l.strip()][-K:]
    except FileNotFoundError:
        return None
    return rows if len(rows) >= 10 else None


def scores_and_r(rows):
    """Return ({i: (score, mean_rtt)}, r, [unresponsive ids]).

    Identical to the Transformer daemon except for the two lines that produce
    `sc`: there a forward pass, here one comparison.
    """
    out, unresp = {}, []
    for i in range(1, N + 1):
        col = i
        try:
            r = np.array([float(x[col]) for x in rows], dtype=np.float64)
        except (IndexError, ValueError):
            continue
        tail = r[-UNRESP_W:]
        if len(tail) and (tail >= UNRESP_MS).mean() >= UNRESP_FRAC:
            unresp.append(i)
        # The detector: mean RTT over the window, thresholded.  Samples pinned
        # at the connect-failure sentinel are excluded so that a *paused* node
        # is not scored as a *slow* one -- that distinction is r's job, and the
        # Transformer daemon leaves it to r as well.
        live = r[r < RTT_FAIL]
        mean_rtt = float(live.mean()) if len(live) else float(r.mean())
        sc = SCORE_RISKY if mean_rtt >= RTT_CUT else SCORE_HEALTHY
        out[i] = (sc, float(r[-5:].mean()))
    return out, len(unresp), unresp


seq = 5000
lg = open(LOG, "a", buffering=1)
lg.write("# meanrtt daemon start thresh=%s N=%d f=%d rtt_cut=%s cap_rule=f-r-1 ts=%.3f\n"
         % (THRESH, N, F, RTT_CUT, time.time()))

last_beat = 0.0
while True:
  try:
    rows = read_rows()
    if time.time() - last_beat > 10:
        lg.write("%.3f heartbeat rows=%s\n" % (time.time(), len(rows) if rows else 0))
        last_beat = time.time()
    if rows:
        s, r, unresp = scores_and_r(rows)
        if s:
            cap = max(0, F - r - 1)
            cand = sorted([i for i in s if s[i][0] < THRESH and i not in unresp],
                          key=lambda i: s[i][0])
            risky = cand[:cap]
            seq += 1
            payload = json.dumps({"blacklist": risky, "seq": seq, "fail_open": False,
                                  "r": r, "cap": cap, "unresponsive": unresp,
                                  "detector": "mean-rtt-threshold",
                                  "scores": {i: round(s[i][0], 3) for i in s}})
            with open(BT, "w") as fh:
                fh.write(payload)
            lg.write("%.3f Bt=%s r=%d cap=%d unresp=%s scores=%s\n"
                     % (time.time(), risky, r, cap, unresp,
                        " ".join("o%d:%.2f(rtt%.0f)" % (i, s[i][0], s[i][1]) for i in s)))
  except Exception as exc:
    lg.write("%.3f ERROR %s: %s\n" % (time.time(), type(exc).__name__, exc))
  time.sleep(PERIOD)
