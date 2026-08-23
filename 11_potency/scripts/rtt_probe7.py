"""In-network RTT probe for the seven-orderer cluster.

rtt_probe.py covers orderers 1-5 and would leave the closed-loop daemon with
five columns where it expects seven -- the feed would parse, the last two
orderers would simply never be scored, and nothing would report an error.  The
cluster ports below were read from the running containers rather than assumed.

Every PERIOD seconds, measure TCP connect RTT to each orderer's cluster port and
append a CSV row to the mounted feed. A failed connect records the timeout value
rather than being dropped, so a node that stops answering shows up as a very
slow node instead of as a gap the window builder would silently shorten.
"""
import os
import socket
import time

PEERS = {
    1: ("orderer.example.com", 7050),
    2: ("orderer2.example.com", 8050),
    3: ("orderer3.example.com", 10050),
    4: ("orderer4.example.com", 11050),
    5: ("orderer5.example.com", 12050),
    6: ("orderer6.example.com", 13050),
    7: ("orderer7.example.com", 14050),
}
FEED = os.environ.get("FEED", "/feed/rtt_feed.csv")
PERIOD = float(os.environ.get("PERIOD", "0.3"))
TIMEOUT = float(os.environ.get("TIMEOUT", "3.0"))


def rtt(host, port):
    t0 = time.perf_counter()
    try:
        s = socket.create_connection((host, port), timeout=TIMEOUT)
        s.close()
        return (time.perf_counter() - t0) * 1000.0
    except Exception:
        return TIMEOUT * 1000.0


os.makedirs(os.path.dirname(FEED), exist_ok=True)
with open(FEED, "a", buffering=1) as f:
    while True:
        row = ["%.3f" % time.time()] + ["%.2f" % rtt(*PEERS[i]) for i in sorted(PEERS)]
        f.write(",".join(row) + "\n")
        time.sleep(PERIOD)
