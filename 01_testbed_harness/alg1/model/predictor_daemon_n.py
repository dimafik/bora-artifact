"""BORA predictor daemon, X1 version (ML in the loop, spec-conformant cap).

Differences from predictor_daemon.py, all required by the X1 design:

  1. Parametric N.  The original hardcoded five orderers (range(1,6)), so it
     could not drive an N=7 cluster.

  2. Spec-conformant cap.  Algorithm 1 substep (c) is
         B_t <- top(p_t, H_t, f - r - 1)
     where r is the Raft-observed unhealthy count (Definition 1).  The original
     applied a static [:FCAP] with FCAP=2, which both ignored r and admitted
     |B_t| = f rather than |B_t| < f.  Both are fixed here.

  3. r derived from follower-observable telemetry.  The paper specifies
     "collapsed ack-rate or stalled replication-lag"; the deployed telemetry is
     the in-network RTT probe, whose connect failures surface as the RTT_FAIL
     sentinel.  An orderer counts toward r when its recent samples are pinned at
     that sentinel, which is exactly what a paused or crashed node produces.

  4. Per-cycle audit trail.  Every cycle logs r, the applied cap and the emitted
     B_t, so each forced election can be checked against the cap the paper
     claims is enforced at emission.

Usage:  python predictor_daemon_n.py [thresh] [N] [f]
        e.g. python predictor_daemon_n.py 0.65 7 3
"""
import sys, os, json, time, numpy as np, torch

sys.path.insert(0, "predictor")
from model import ScorePredictor, CONFIG

FEED = r"D:\fabric-d2\results\rtt_feed.csv"
BT = r"D:\fabric-d2\results\bt.json"
LOG = r"D:\fabric-d2\results\predictor_daemon.log"

K = CONFIG.window_len
ALPHA = 0.8
PERIOD = 0.5

THRESH = float(sys.argv[1]) if len(sys.argv) > 1 else 0.65   # score below -> risky
N = int(sys.argv[2]) if len(sys.argv) > 2 else 5             # cluster size
F = int(sys.argv[3]) if len(sys.argv) > 3 else (N - 1) // 2  # tolerated faults

# --- r detection -------------------------------------------------------------
RTT_FAIL = 1500.0     # sentinel written by rtt_probe_n.py on connect failure
UNRESP_MS = 1000.0    # a sample at or above this counts as "no response"
UNRESP_W = 6          # look at the last UNRESP_W samples
UNRESP_FRAC = 0.5     # unhealthy if at least this fraction are unresponsive

m = ScorePredictor(CONFIG)
sd = torch.load("model_small/best.pt", map_location="cpu")
state = sd.get("model_state_dict", sd.get("state_dict", sd)) if isinstance(sd, dict) else sd
m.load_state_dict(state)
m.eval()


def window(r):
    n = len(r)
    RTT = np.empty(n)
    RTT[0] = r[0]
    for t in range(1, n):
        RTT[t] = ALPHA * RTT[t - 1] + (1 - ALPHA) * r[t]
    Tc = np.full(n, 100.0)
    cc = (r <= Tc).astype(float)
    CC = np.convolve(cc, np.ones(min(20, n)) / min(20, n), mode="same")
    dCC = np.diff(CC, prepend=CC[0])
    dRTT = np.diff(RTT, prepend=RTT[0])
    dz = np.zeros(n)
    return np.stack([cc, CC, r, RTT, Tc, dCC, dRTT, dz], axis=1).astype(np.float32)


def read_rows():
    try:
        rows = [l.strip().split(",") for l in open(FEED).read().splitlines() if l.strip()][-K:]
    except FileNotFoundError:
        return None
    return rows if len(rows) >= 10 else None


def scores_and_r(rows):
    """Return ({i: (score, mean_rtt)}, r, [unresponsive ids])."""
    out, unresp = {}, []
    for i in range(1, N + 1):
        col = i  # column 0 is the timestamp
        try:
            r = np.array([float(x[col]) for x in rows], dtype=np.float64)
        except (IndexError, ValueError):
            continue
        # r: Raft-observed unhealthy count, from follower-observable telemetry
        tail = r[-UNRESP_W:]
        if len(tail) and (tail >= UNRESP_MS).mean() >= UNRESP_FRAC:
            unresp.append(i)
        X = window(r)
        with torch.no_grad():
            sc = float(m(torch.from_numpy(X).unsqueeze(0))["score"][0, 0, 1])
        out[i] = (sc, float(r[-5:].mean()))
    return out, len(unresp), unresp


seq = 5000
lg = open(LOG, "a", buffering=1)
lg.write("# daemon start thresh=%s N=%d f=%d cap_rule=f-r-1 ts=%.3f\n"
         % (THRESH, N, F, time.time()))

# The daemon must outlive every transient fault.  It died once mid-experiment on
# an unhandled PermissionError and the run continued for minutes with a stale
# bt.json and no error visible anywhere; the arm that depends on it was silently
# worthless.  Anything raised inside a cycle is logged and the loop continues, and
# a heartbeat line is emitted even when nothing is published so a stall is
# distinguishable from an idle feed.
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
            # Algorithm 1 substep (c): hard cap |B_t| < f - r
            cap = max(0, F - r - 1)
            # An unresponsive node is already down; it is not a candidate to suppress.
            cand = sorted([i for i in s if s[i][0] < THRESH and i not in unresp],
                          key=lambda i: s[i][0])
            risky = cand[:cap]
            seq += 1
            # Publish in ONE write call.
            #
            # An earlier version wrote to bt.json.tmp and os.replace()d it, to stop
            # the pusher reading a half-written file.  On Windows that raises
            # PermissionError [WinError 5] as soon as the WSL-side pusher has the
            # destination open -- which it does every 0.3 s -- and the daemon died
            # mid-run with the experiment still going.  Cross-process rename
            # atomicity is not available here.
            #
            # json.dumps + a single fh.write() of a few hundred bytes is one write
            # syscall, so a reader doing one read cannot interleave with it. The
            # pusher additionally keeps its last good value on a parse failure, so
            # even a torn read never clears the blacklist.
            payload = json.dumps({"blacklist": risky, "seq": seq, "fail_open": False,
                                  "r": r, "cap": cap, "unresponsive": unresp,
                                  "scores": {i: round(s[i][0], 3) for i in s}})
            with open(BT, "w") as fh:
                fh.write(payload)
            lg.write("%.3f Bt=%s r=%d cap=%d unresp=%s scores=%s\n"
                     % (time.time(), risky, r, cap, unresp,
                        " ".join("o%d:%.2f(rtt%.0f)" % (i, s[i][0], s[i][1]) for i in s)))
  except Exception as exc:
    lg.write("%.3f ERROR %s: %s\n" % (time.time(), type(exc).__name__, exc))
  time.sleep(PERIOD)
