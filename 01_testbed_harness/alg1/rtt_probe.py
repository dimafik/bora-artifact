"""In-network RTT probe. Runs in a python:slim container on the fabric_test
network. Every PERIOD seconds, measures TCP connect RTT to each orderer's
internal cluster port and appends a CSV row to a mounted feed file. This is the
live telemetry source the BORA predictor consumes (the host daemon has torch)."""
import socket, time, os
PEERS = {1: ("orderer.example.com", 7050), 2: ("orderer2.example.com", 8050),
         3: ("orderer3.example.com", 10050), 4: ("orderer4.example.com", 11050),
         5: ("orderer5.example.com", 12050)}
FEED = os.environ.get("FEED", "/feed/rtt_feed.csv")
PERIOD = float(os.environ.get("PERIOD", "0.3"))

def rtt(host, port):
    t0 = time.perf_counter()
    try:
        s = socket.create_connection((host, port), timeout=1.5); s.close()
        return (time.perf_counter() - t0) * 1000.0
    except Exception:
        return 1500.0

os.makedirs(os.path.dirname(FEED), exist_ok=True)
with open(FEED, "a", buffering=1) as f:
    while True:
        row = [f"{time.time():.3f}"] + [f"{rtt(*PEERS[i]):.2f}" for i in sorted(PEERS)]
        f.write(",".join(row) + "\n")
        time.sleep(PERIOD)
