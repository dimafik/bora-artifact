"""Feasibility gate: does the trained Transformer discriminate the attacked
orderer from LIVE RTT telemetry? Collect per-orderer connect RTT to the
published cluster ports, build the 8-feature window the model was trained on,
run best.pt, and print per-orderer predicted Score + anomaly."""
import socket, time, sys
import numpy as np
import torch
sys.path.insert(0, "predictor")
from model import ScorePredictor, CONFIG

# host-published cluster ports
PORTS = {1: 7050, 2: 8050, 3: 10050, 4: 11050, 5: 12050}
HOST = "127.0.0.1"
K = CONFIG.window_len   # 60
ALPHA = 0.8

def rtt_ms(port):
    t0 = time.perf_counter()
    try:
        s = socket.create_connection((HOST, port), timeout=2.0); s.close()
        return (time.perf_counter() - t0) * 1000
    except Exception:
        return 2000.0

# collect K ticks
print(f"collecting {K} ticks of RTT (~{K*0.4:.0f}s)...")
raw = {i: [] for i in PORTS}
for _ in range(K):
    for i, p in PORTS.items():
        raw[i].append(rtt_ms(p))
    time.sleep(0.3)

m = ScorePredictor(CONFIG)
sd = torch.load("model_small/best.pt", map_location="cpu")
state = sd.get("model_state_dict", sd.get("state_dict", sd)) if isinstance(sd, dict) else sd
m.load_state_dict(state); m.eval()

def build_window(rtts):
    rtts = np.array(rtts, dtype=np.float64)
    RTT = np.empty(K); RTT[0] = rtts[0]
    for t in range(1, K):
        RTT[t] = ALPHA * RTT[t-1] + (1 - ALPHA) * rtts[t]
    T_commit = np.full(K, 100.0)
    cc_inst = (rtts <= T_commit).astype(float)
    CC = np.convolve(cc_inst, np.ones(min(20, K))/min(20, K), mode="same")
    dCC = np.diff(CC, prepend=CC[0]); dRTT = np.diff(RTT, prepend=RTT[0])
    design = np.zeros(K)
    X = np.stack([cc_inst, CC, rtts, RTT, T_commit, dCC, dRTT, design], axis=1)
    return X.astype(np.float32)

print(f"\n{'node':>4} {'meanRTT':>8} {'score30':>8} {'anomaly':>8}")
for i in PORTS:
    X = build_window(raw[i])
    with torch.no_grad():
        out = m(torch.from_numpy(X).unsqueeze(0))
    score30 = float(out["score"][0, 0, 1])   # horizon0, median quantile
    anom = float(torch.sigmoid(out["anomaly"])[0, 0]) if out["anomaly"].abs().max() > 1 else float(out["anomaly"][0, 0])
    print(f"o{i:>3} {np.mean(raw[i]):8.1f} {score30:8.3f} {anom:8.3f}")
