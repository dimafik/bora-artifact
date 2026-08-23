#!/usr/bin/env bash
# ML-in-the-loop detection experiment (WSL side). Assumes the host predictor
# daemon (torch) is already running and consuming the RTT feed. Starts the
# in-network probe + advice pusher, runs a baseline, injects a +500ms attack on
# orderer3 at a recorded T0, holds, then heals. The predictor's bt.json log
# gives detection latency + accuracy.
set -u
source /mnt/d/fabric-d2/alg1/sidecar_lib.sh
R=/mnt/d/fabric-d2/results
OUT="$R/mldetect_$(date +%Y%m%d-%H%M%S)"; mkdir -p "$OUT"
rm -f "$R/rtt_feed.csv"; echo '{"blacklist":[],"seq":1}' > "$R/bt.json"
docker rm -f rtt-probe pumba-ml >/dev/null 2>&1

echo "[0] ensure v3 sidecars + advice empty" | tee "$OUT/timeline.txt"
ensure_all_sidecars
for o in "${ALL_ORD[@]}"; do docker exec "$o" sh -c 'printf "%s" "{\"blacklist\":[],\"seq\":1,\"fail_open\":false}" > /tmp/bora-advice.json' 2>/dev/null; done

echo "[1] start in-network RTT probe" | tee -a "$OUT/timeline.txt"
docker run -d --name rtt-probe --network fabric_test -v /mnt/d/fabric-d2:/feed \
  -v /mnt/d/fabric-d2/alg1/rtt_probe.py:/rtt_probe.py -e FEED=/feed/results/rtt_feed.csv \
  python:3.11-slim python /rtt_probe.py >/dev/null 2>&1

echo "[2] start advice pusher" | tee -a "$OUT/timeline.txt"
rm -f /tmp/push.on; bash /mnt/d/fabric-d2/alg1/push_advice.sh >"$OUT/pusher.log" 2>&1 &
PUSH=$!

echo "[3] baseline 14s (no attack; expect Bt empty)" | tee -a "$OUT/timeline.txt"
sleep 14
T0=$(date +%s.%N)
echo "ATTACK_ONSET_T0=$T0" | tee -a "$OUT/timeline.txt"
docker run -d --name pumba-ml -v /var/run/docker.sock:/var/run/docker.sock gaiaadm/pumba:latest \
  --interval 5m --log-level warning netem --tc-image gaiadocker/iproute2 --duration 4m \
  delay --time 500 orderer3.example.com >/dev/null 2>&1

echo "[4] hold attack 50s (predictor should flag o3)" | tee -a "$OUT/timeline.txt"
sleep 50
T1=$(date +%s.%N); echo "ATTACK_STOP_T1=$T1" | tee -a "$OUT/timeline.txt"
docker stop pumba-ml >/dev/null 2>&1   # SIGTERM -> pumba reverts netem cleanly
docker rm -f pumba-ml >/dev/null 2>&1

echo "[5] recovery 20s (predictor should clear o3)" | tee -a "$OUT/timeline.txt"
sleep 20

echo "[6] stop" | tee -a "$OUT/timeline.txt"
rm -f /tmp/push.on; kill $PUSH 2>/dev/null
docker rm -f rtt-probe >/dev/null 2>&1
cp "$R/predictor_daemon.log" "$OUT/" 2>/dev/null
echo "ML_DETECT_DONE OUT=$OUT" | tee -a "$OUT/timeline.txt"
