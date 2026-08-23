#!/bin/bash
# Concurrency sweep v2 — takes seed and N_TX as explicit positional args
# Args: $1=seed $2=n_tx_per_thread $3=output_root
set -e
SEED=${1:-1}
N_TX=${2:-20}
ROOT=${3:-/mnt/d/fabric-d2/results_5node}

cd /mnt/d/fabric-d2/fabric-samples/test-network
export PATH=/tmp/bin:/tmp/go-install/go/bin:/mnt/d/fabric-d2/fabric-samples/bin-linux/bin:/usr/local/bin:/usr/bin:/bin
export FABRIC_CFG_PATH=/mnt/d/fabric-d2/fabric-samples/config
export CORE_PEER_TLS_ENABLED=true
export CORE_PEER_LOCALMSPID="Org1MSP"
TESTNET=/mnt/d/fabric-d2/fabric-samples/test-network
export CORE_PEER_TLS_ROOTCERT_FILE=$TESTNET/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt
export CORE_PEER_MSPCONFIGPATH=$TESTNET/organizations/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp
export CORE_PEER_ADDRESS=localhost:7051

ORDERER_CAFILE="${TESTNET}/organizations/ordererOrganizations/example.com/orderers/orderer.example.com/msp/tlscacerts/tlsca.example.com-cert.pem"
PEER1_TLS="${TESTNET}/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt"
PEER2_TLS="${TESTNET}/organizations/peerOrganizations/org2.example.com/peers/peer0.org2.example.com/tls/ca.crt"

run_thread() {
  local tid=$1; local seed=$2; local n=$3; local out=$4
  for i in $(seq 1 "$n"); do
    local asset="bench_s${seed}_t${tid}_${i}_$$"
    local t0=$(($(date +%s%N) / 1000000))
    if peer chaincode invoke \
        -o localhost:7050 \
        --ordererTLSHostnameOverride orderer.example.com \
        --tls --cafile "$ORDERER_CAFILE" \
        -C mychannel -n basic \
        --peerAddresses localhost:7051 --tlsRootCertFiles "$PEER1_TLS" \
        --peerAddresses localhost:9051 --tlsRootCertFiles "$PEER2_TLS" \
        -c "{\"function\":\"CreateAsset\",\"Args\":[\"${asset}\",\"red\",\"100\",\"alice\",\"42\"]}" \
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

OUTDIR=$ROOT/seed${SEED}/conc_sweep
mkdir -p "$OUTDIR"
SUMMARY="$OUTDIR/summary.csv"
echo "concurrency,duration_ms,ok,fail,tps_total,mean_latency_ms,p50,p95,p99,max" > "$SUMMARY"

for C in 1 2 4 8 16; do
  RUN_DIR="$OUTDIR/c${C}"
  mkdir -p "$RUN_DIR"
  rm -f "$RUN_DIR"/t*.csv
  T_START=$(date +%s%N)
  for tid in $(seq 1 "$C"); do
    OUT_T="$RUN_DIR/t${tid}.csv"
    : > "$OUT_T"
    ( run_thread "$tid" "$SEED" "$N_TX" "$OUT_T" ) &
  done
  wait
  T_END=$(date +%s%N)
  DUR=$(( (T_END - T_START) / 1000000 ))

  MERGED="$RUN_DIR/merged.csv"
  echo "thread,tx_idx,start_ms,end_ms,latency_ms,status" > "$MERGED"
  cat "$RUN_DIR"/t*.csv >> "$MERGED" 2>/dev/null

  OK=$(awk -F',' 'NR>1 && $6=="OK"' "$MERGED" | wc -l)
  FAIL=$(awk -F',' 'NR>1 && $6=="FAIL"' "$MERGED" | wc -l)
  TPS=$(awk "BEGIN { printf \"%.2f\", $OK / ($DUR / 1000.0) }")

  read -r MEAN P50 P95 P99 MAX <<< "$(
    awk -F',' 'NR>1 && $6=="OK" { print $5 }' "$MERGED" | sort -n | \
    awk -v n="$OK" '
      { a[NR]=$1; s+=$1 }
      END {
        if (n==0) { print "0 0 0 0 0"; exit }
        p50=a[int(n*0.50)+1]; p95=a[int(n*0.95)+1]; p99=a[int(n*0.99)+1]; max=a[n]
        printf "%.1f %d %d %d %d", s/n, p50, p95, p99, max
      }')"

  echo "${C},${DUR},${OK},${FAIL},${TPS},${MEAN},${P50},${P95},${P99},${MAX}" >> "$SUMMARY"
  echo "SEED=$SEED C=$C dur=${DUR}ms ok=${OK} fail=${FAIL} TPS=${TPS} p99=${P99}ms"
done
