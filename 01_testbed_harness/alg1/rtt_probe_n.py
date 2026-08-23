"""In-network RTT probe, parametric in N (X1 version).

Same measurement as rtt_probe.py, but the peer table is generated from N so the
same probe serves the whole X1 sweep (N = 7, 9, 11, 15, 21). Port scheme matches
nsweep.sh gport() and gen_nnode.py PORT:
  orderer1 = 7050, orderer2 = 8050, orderer_i = 10050 + 1000*(i-3) for i >= 3
9050 is skipped because the peers and orderer CA own 9051/9052/9054.

A failed connect returns the sentinel RTT_FAIL (ms). The BORA predictor daemon
uses that sentinel to derive r, the Raft-observed unhealthy count, which caps the
blacklist at |B_t| < f - r (Definition 1, Algorithm 1 substep (c)).
"""
import socket, time, os

N = int(os.environ.get("N", "5"))
FEED = os.environ.get("FEED", "/feed/rtt_feed.csv")
PERIOD = float(os.environ.get("PERIOD", "0.3"))
TIMEOUT = float(os.environ.get("TIMEOUT", "1.5"))
RTT_FAIL = 1500.0                      # sentinel: connect failed / node unreachable

MAXN = 21
GPORT = {1: 7050, 2: 8050}
GPORT.update({i: 10050 + 1000 * (i - 3) for i in range(3, MAXN + 1)})
assert N in GPORT, "N=%d exceeds the port table (MAXN=%d)" % (N, MAXN)


def host(i):
    return "orderer.example.com" if i == 1 else "orderer%d.example.com" % i


PEERS = {i: (host(i), GPORT[i]) for i in range(1, N + 1)}


def rtt(h, p):
    t0 = time.perf_counter()
    try:
        s = socket.create_connection((h, p), timeout=TIMEOUT)
        s.close()
        return (time.perf_counter() - t0) * 1000.0
    except Exception:
        return RTT_FAIL


os.makedirs(os.path.dirname(FEED), exist_ok=True)
with open(FEED, "a", buffering=1) as f:
    while True:
        row = ["%.3f" % time.time()] + ["%.2f" % rtt(*PEERS[i]) for i in sorted(PEERS)]
        f.write(",".join(row) + "\n")
        time.sleep(PERIOD)
