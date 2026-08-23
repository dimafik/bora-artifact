#!/bin/bash
# NE26: Algorithm 1 actual end-to-end measurement (λ campaign).
# Compares:
#   Phase A: +200ms attack on orderer3 WITHOUT Algorithm 1 (== NE21/NE22-A baseline)
#   Phase C: +200ms attack on orderer3 WITH Algorithm 1 sidecar active
#            (the actual paper mechanism: bounded blacklist + ALR + fail-open)
set -e

RESULTS=/mnt/d/fabric-d2/results_alg1_real
rm -rf "$RESULTS"
mkdir -p "$RESULTS"

CTRL=/mnt/d/fabric-d2/alg1
LOG_DIR="$RESULTS/sidecar_logs"
mkdir -p "$LOG_DIR"

echo "##################################################"
echo "###### λ Step 1: Fresh 5-orderer Raft ############"
echo "##################################################"
bash /mnt/d/fabric-d2/fresh-network.sh 2>&1 | tail -3

# --- Phase A baseline (no Algorithm 1) ---
echo ""
echo "##################################################"
echo "###### λ Phase A: attack, NO Algorithm 1 #########"
echo "##################################################"
docker run -d --name pumba-lam-A -v /var/run/docker.sock:/var/run/docker.sock \
  gaiaadm/pumba:latest --interval 10m --log-level info \
  netem --tc-image gaiadocker/iproute2 --duration 4m \
  delay --time 200 orderer3.example.com 2>&1 | tail -1
sleep 5
for s in 1 2 3; do
  bash /mnt/d/fabric-d2/concurrency-sweep-v2.sh "$s" 15 "$RESULTS/phaseA_attack_only"
done
docker rm -f pumba-lam-A 2>&1 | tail -1 || true
sleep 5

# --- Phase C: SAME attack but with Algorithm 1 sidecar live ---
echo ""
echo "##################################################"
echo "###### λ Phase C: attack + Algorithm 1 sidecar ###"
echo "##################################################"

# Step 1: Start sidecar FIRST on clean network (warm-up its window)
SIDECAR_LOG="$LOG_DIR/sidecar.log"
echo "Starting Algorithm 1 sidecar (log: $SIDECAR_LOG)"
nohup python3 "$CTRL/sidecar.py" --config "$CTRL/alg1.yaml" \
  --log "$SIDECAR_LOG" > "$LOG_DIR/sidecar_stdout.log" 2>&1 &
SIDECAR_PID=$!
echo "Sidecar PID: $SIDECAR_PID; warm-up 20s on clean cluster..."
sleep 20
echo "[warm-up done] sidecar tail:"
tail -5 "$SIDECAR_LOG"

# Step 2: Now inject attack — sidecar already has clean baseline
docker run -d --name pumba-lam-C -v /var/run/docker.sock:/var/run/docker.sock \
  gaiaadm/pumba:latest --interval 10m --log-level info \
  netem --tc-image gaiadocker/iproute2 --duration 4m \
  delay --time 200 orderer3.example.com 2>&1 | tail -1

# Step 3: Let sidecar detect (need ~10s for log-activity divergence to register)
echo "Attack injected; letting sidecar detect for 15s..."
sleep 15
echo "[after detection] sidecar tail:"
tail -10 "$SIDECAR_LOG"
echo "[advice events so far]:"
grep -c YIELD "$SIDECAR_LOG" || echo 0

# Step 4: Run sweep under sidecar protection
for s in 1 2 3; do
  bash /mnt/d/fabric-d2/concurrency-sweep-v2.sh "$s" 15 "$RESULTS/phaseC_attack_with_alg1"
done

echo "Stopping sidecar..."
kill -INT $SIDECAR_PID 2>/dev/null || true
sleep 3
docker rm -f pumba-lam-C 2>&1 | tail -1 || true

# Make sure all orderers are unpaused
for c in orderer.example.com orderer2.example.com orderer3.example.com \
         orderer4.example.com orderer5.example.com; do
  docker unpause "$c" 2>/dev/null || true
done

echo ""
echo "##################################################"
echo "########### λ AGGREGATE COMPARISON ###############"
echo "##################################################"
python3 << PYEOF
import csv, os, statistics as st
phases = [("phaseA_attack_only", "Phase A: attack, no Alg 1"),
          ("phaseC_attack_with_alg1", "Phase C: attack + Alg 1 (this work)")]
print(f"{'phase':<32} {'C':>3} {'TPS_mean':>9} {'TPS_std':>8} {'p99_mean':>9} {'fails':>6}")
print("-" * 78)
for phase, label in phases:
    by_c = {}
    for s in [1,2,3]:
        f = f"$RESULTS/{phase}/seed{s}/conc_sweep/summary.csv"
        if not os.path.exists(f): continue
        with open(f) as fp:
            for row in csv.DictReader(fp):
                if row.get("tps_total") and row["tps_total"].strip():
                    by_c.setdefault(row["concurrency"], []).append(row)
    for c in sorted(by_c, key=int):
        tps = [float(r["tps_total"]) for r in by_c[c]]
        p99 = [float(r["p99"]) for r in by_c[c] if r.get("p99") and r["p99"].strip()]
        fails = sum(int(r.get("fail",0) or 0) for r in by_c[c])
        m = st.mean(tps); sd = st.stdev(tps) if len(tps)>1 else 0
        p = st.mean(p99) if p99 else 0
        print(f"{label:<32} {c:>3} {m:>9.2f} {sd:>8.2f} {p:>9.1f} {fails:>6d}")
PYEOF

echo ""
echo "############ SIDECAR STATS ##########"
grep -E "advice_events|safety_violations|Final stats" "$SIDECAR_LOG" | tail -10
echo ""
echo "############ FIRST advice EVENTS ##########"
grep -E "YIELD|UNYIELD" "$SIDECAR_LOG" | head -20
