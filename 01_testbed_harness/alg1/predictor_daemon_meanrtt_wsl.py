"""B-20 arm: the same BORA advisor with a zero-parameter detector, WSL-side.

Identical in behaviour to predictor_daemon_meanrtt.py. Two differences, both
about where it runs rather than what it decides:

  * Paths are /mnt/d/... rather than D:\\..., so the driver can start it from
    the same shell that runs the harness. Launching it through WSL's PowerShell
    interop does not work: Start-Process hands the daemon a handle the interop
    shim then waits on, so the caller blocks forever on a daemon that is
    supposed to outlive it. That cost one sweep launch.

  * No numpy. WSL's python has none, and this detector needs a mean and a
    comparison. Installing a package to compute an average would be a worse
    trade than four lines of arithmetic.

Everything that decides anything -- the feed window, the r derivation, the
Algorithm 1 cap |B_t| < f - r, the advice payload and the log format -- is the
same as the Transformer daemon, so a difference in outcome is a difference in
the detector and not in the envelope around it.

Usage:  python3 predictor_daemon_meanrtt_wsl.py [thresh] [N] [f] [rtt_cut_ms]
"""
import sys, json, time

R = "/mnt/d/fabric-d2/results"
FEED = R + "/rtt_feed.csv"
BT = R + "/bt.json"
LOG = R + "/predictor_daemon_meanrtt.log"

K = 64
PERIOD = 0.5

THRESH = float(sys.argv[1]) if len(sys.argv) > 1 else 0.65
N = int(sys.argv[2]) if len(sys.argv) > 2 else 5
F = int(sys.argv[3]) if len(sys.argv) > 3 else (N - 1) // 2
RTT_CUT = float(sys.argv[4]) if len(sys.argv) > 4 else 50.0

RTT_FAIL = 1500.0
UNRESP_MS = 1000.0
UNRESP_W = 6
UNRESP_FRAC = 0.5

SCORE_HEALTHY = 0.85
SCORE_RISKY = 0.42


def read_rows():
    try:
        with open(FEED) as fh:
            rows = [l.strip().split(",") for l in fh.read().splitlines() if l.strip()][-K:]
    except FileNotFoundError:
        return None
    return rows if len(rows) >= 10 else None


def scores_and_r(rows):
    out, unresp = {}, []
    for i in range(1, N + 1):
        try:
            r = [float(x[i]) for x in rows]
        except (IndexError, ValueError):
            continue
        tail = r[-UNRESP_W:]
        if tail and sum(1 for v in tail if v >= UNRESP_MS) / float(len(tail)) >= UNRESP_FRAC:
            unresp.append(i)
        live = [v for v in r if v < RTT_FAIL]
        mean_rtt = (sum(live) / len(live)) if live else (sum(r) / len(r))
        sc = SCORE_RISKY if mean_rtt >= RTT_CUT else SCORE_HEALTHY
        last5 = r[-5:]
        out[i] = (sc, sum(last5) / len(last5))
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
