#!/bin/bash
# Concurrency sweep: measures throughput-vs-latency at C={1,2,4,8,16} clients.
# Each concurrency level runs N_TX_PER_THREAD transactions per thread.
set -e
cd /mnt/d/fabric-d2/fabric-samples/test-network
export PATH=/tmp/bin:/tmp/go-install/go/bin:/mnt/d/fabric-d2/fabric-samples/bin-linux/bin:/usr/local/bin:/usr/bin:/bin
export FABRIC_CFG_PATH=/mnt/d/fabric-d2/fabric-samples/config
export CORE_PEER_TLS_ENABLED=true
export CORE_PEER_LOCALMSPID="Org1MSP"
export CORE_PEER_TLS_ROOTCERT_FILE=$PWD/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt
export CORE_PEER_MSPCONFIGPATH=$PWD/organizations/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp
export CORE_PEER_ADDRESS=localhost:7051

ORDERER_CAFILE="${PWD}/organizations/ordererOrganizations/example.com/orderers/orderer.example.com/msp/tlscacerts/tlsca.example.com-cert.pem"
PEER1_TLS="${PWD}/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt"
PEER2_TLS="${PWD}/organizations/peerOrganizations/org2.example.com/peers/peer0.org2.example.com/tls/ca.crt"

# Per-thread worker. Args: thread_id seed n_tx_per_thread output_csv
run_thread() {
  local tid=$1
  local seed=$2
  local n_tx=$3
  local out=$4
  for i in $(seq 1 "$n_tx"); do
    local asset_id="bench_s${seed}_t${tid}_${i}_$$"
    local t0=$(($(date +%s%N) / 1000000))
    if peer chaincode invoke \
        -o localhost:7050 \
        --ordererTLSHostnameOverride orderer.example.com \
        --tls --cafile "$ORDERER_CAFILE" \
        -C mychannel -n basic \
        --peerAddresses localhost:7051 --tlsRootCertFiles "$PEER1_TLS" \
        --peerAddresses localhost:9051 --tlsRootCertFiles "$PEER2_TLS" \
        -c "{\"function\":\"CreateAsset\",\"Args\":[\"${asset_id}\",\"red\",\"100\",\"alice\",\"42\"]}" \
        >/dev/null 2>&1; then
      local t1=$(($(date +%s%N) / 1000000))
      echo "${tid},${i},${t0},${t1},$((t1 - t0)),OK" >> "$out"
    else
      local t1=$(($(date +%s%N) / 1000000))
      echo "${tid},${i},${t0},${t1},$((t1 - t0)),FAIL" >> "$out"
    fi
  done
}
export -f run_thread
export ORDERER_CAFILE PEER1_TLS PEER2_TLS

SEED=${SEED:-1}
N_TX_PER_THREAD=${N_TX_PER_THREAD:-30}
OUTDIR=/mnt/d/fabric-d2/results/seed${SEED}/conc_sweep
mkdir -p "$OUTDIR"

SUMMARY="$OUTDIR/summary.csv"
echo "concurrency,duration_ms,ok,fail,tps_total,mean_latency_ms,p50,p95,p99,max" > "$SUMMARY"

for C in 1 2 4 8 16; do
  echo ""
  echo "=== Concurrency $C, seed $SEED, $N_TX_PER_THREAD tx/thread ==="
  RUN_DIR="$OUTDIR/c${C}"
  mkdir -p "$RUN_DIR"
  # Per-thread CSVs
  T_START=$(date +%s%N)
  for tid in $(seq 1 "$C"); do
    OUT_T="$RUN_DIR/t${tid}.csv"
    : > "$OUT_T"
    ( run_thread "$tid" "$SEED" "$N_TX_PER_THREAD" "$OUT_T" ) &
  done
  wait
  T_END=$(date +%s%N)
  DURATION_MS=$(( (T_END - T_START) / 1000000 ))

  # Merge
  MERGED="$RUN_DIR/merged.csv"
  echo "thread,tx_idx,start_ms,end_ms,latency_ms,status" > "$MERGED"
  cat "$RUN_DIR"/t*.csv >> "$MERGED"
  OK=$(grep -c ',OK$' "$MERGED" || echo 0)
  FAIL=$(grep -c ',FAIL$' "$MERGED" || echo 0)
  TPS=$(awk "BEGIN { printf \"%.2f\", $OK / ($DURATION_MS / 1000.0) }")

  read -r MEAN P50 P95 P99 MAX <<< "$(
    awk -F',' 'NR>1 && $6=="OK" { print $5 }' "$MERGED" | sort -n | \
    awk -v n="$OK" '
      { a[NR]=$1; s+=$1 }
      END {
        if (n==0) { print "0 0 0 0 0"; exit }
        p50=a[int(n*0.50)+1]; p95=a[int(n*0.95)+1]; p99=a[int(n*0.99)+1]; max=a[n]
        printf "%.1f %d %d %d %d", s/n, p50, p95, p99, max
      }')"

  echo "${C},${DURATION_MS},${OK},${FAIL},${TPS},${MEAN},${P50},${P95},${P99},${MAX}" >> "$SUMMARY"
  echo "C=$C  dur=${DURATION_MS}ms  ok=${OK}  fail=${FAIL}  TPS=${TPS}  mean=${MEAN}ms  p95=${P95}ms  p99=${P99}ms"
done

echo ""
echo "=== Final summary table ==="
cat "$SUMMARY" | column -t -s,
