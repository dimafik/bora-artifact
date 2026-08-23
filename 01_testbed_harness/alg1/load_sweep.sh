#!/usr/bin/env bash
# Load-threshold characterization of BORA vote-reject (v4). For each sustained
# transaction load L (tx/s), with B_t=[3] standing, run K forced elections and
# count how often orderer3 acquires leadership. Hypothesis: below a load
# threshold the honest voters answer the 50ms advisor dial in time and reject
# every vote -> orderer3 wins 0; above it, missed dials let some votes through
# and the win rate rises (graceful, fail-open degradation).
set -u
source /mnt/d/fabric-d2/alg1/sidecar_lib.sh
K="${K:-10}"
LOADS="${LOADS:-0 100 200 300 400}"
WS=/mnt/d/fabric-d2/caliper-workspace
CRYPTO=/mnt/d/fabric-d2/fabric-samples/test-network/organizations
OUT=/mnt/d/fabric-d2/results/loadsweep_$(date +%Y%m%d-%H%M%S); mkdir -p "$OUT"
ALL=("${ALL_ORD[@]}")
echo "load_tps,orderer3_wins,k,liveness" > "$OUT/results.csv"
RUN=/tmp/ls_heal.on; touch $RUN
( while [ -f $RUN ]; do ensure_all_sidecars; sleep 0.5; done ) & HP=$!
name_for_id(){ case $1 in 1)echo orderer.example.com;;2)echo orderer2.example.com;;3)echo orderer3.example.com;;4)echo orderer4.example.com;;5)echo orderer5.example.com;;*)echo "";;esac; }
set_all(){ for o in "${ALL[@]}"; do docker exec "$o" sh -c "printf '%s' '{\"blacklist\":$1,\"seq\":1,\"fail_open\":false}' > /tmp/bora-advice.json" 2>/dev/null; done; }
leader_id(){ local b=-1 bid=0 id o t; for id in 1 2 3 4 5; do o=$(name_for_id $id); t=$(docker logs --tail 200 "$o" 2>&1 | grep -ao "became leader at term [0-9]*" | tail -1 | grep -ao "[0-9]*$"); [ -n "$t" ]&&[ "$t" -gt "$b" ]&&{ b=$t;bid=$id; }; done; echo $bid; }

gen_bench(){ # $1=tps  -> writes a single long round
  cat > "$WS/benchmarks/_loadgen.yaml" <<YML
test:
  name: loadgen-$1
  workers: {number: 4}
  rounds:
    - label: load-$1
      txDuration: 200
      rateControl: {type: fixed-rate, opts: {tps: $1}}
      workload: {module: workload/createAsset.js}
YML
}
start_load(){ # $1=tps
  [ "$1" = "0" ] && return 0
  gen_bench "$1"
  docker rm -f caliper-load >/dev/null 2>&1 || true
  docker run --rm --name caliper-load --network fabric_test \
    -v "$WS:/hyperledger/caliper/workspace" -v "$CRYPTO:/cryptoMount" \
    --add-host=host.docker.internal:host-gateway \
    -e CALIPER_BIND_SUT=fabric:fabric-gateway \
    -e CALIPER_BENCHCONFIG=benchmarks/_loadgen.yaml \
    -e CALIPER_NETWORKCONFIG=networks/fabric-5node.yaml \
    -e CALIPER_FLOW_ONLY_TEST=true \
    hyperledger/caliper:0.6.0 launch manager > "$OUT/caliper-$1.log" 2>&1 &
  CALPID=$!
  sleep 28   # warm-up so steady-state load overlaps the elections
}
stop_load(){ docker rm -f caliper-load >/dev/null 2>&1 || true; [ "${CALPID:-0}" != "0" ] && kill "$CALPID" 2>/dev/null; CALPID=0; }

set_all "[3]"; sleep 2
for L in $LOADS; do
  echo "######## LOAD $L tx/s ########" | tee -a "$OUT/summary.txt"
  start_load "$L"
  set_all "[3]"   # re-assert in case any sidecar restarted
  w=0; live=0
  for k in $(seq 1 "$K"); do
    Lr=$(leader_id); LC=$(name_for_id $Lr); [ -z "$LC" ]&&LC=orderer2.example.com
    docker restart "$LC" >/dev/null 2>&1; ensure_all_sidecars; sleep 12
    NL=$(leader_id); [ "$NL" = "3" ]&&w=$((w+1)); [ "$NL" != "0" ]&&live=$((live+1))
    echo "[L$L] e$k: $Lr -> $NL" >> "$OUT/elections.log"
  done
  stop_load
  echo "  LOAD $L: orderer3 won $w/$K | liveness $live/$K" | tee -a "$OUT/summary.txt"
  echo "$L,$w,$K,$live" >> "$OUT/results.csv"
done
set_all "[]"; rm -f $RUN; kill $HP 2>/dev/null || true
echo "LOAD_SWEEP_DONE (results: $OUT)" | tee -a "$OUT/summary.txt"
cat "$OUT/results.csv" | tee -a "$OUT/summary.txt"
