#!/bin/bash
# Lightweight throughput/latency baseline for 1-orderer Raft test-network.
set -e
cd /mnt/d/fabric-d2/fabric-samples/test-network
export PATH=/tmp/bin:/tmp/go-install/go/bin:/mnt/d/fabric-d2/fabric-samples/bin-linux/bin:/usr/local/bin:/usr/bin:/bin
export FABRIC_CFG_PATH=/mnt/d/fabric-d2/fabric-samples/config
export CORE_PEER_TLS_ENABLED=true
export CORE_PEER_LOCALMSPID="Org1MSP"
export CORE_PEER_TLS_ROOTCERT_FILE=$PWD/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt
export CORE_PEER_MSPCONFIGPATH=$PWD/organizations/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp
export CORE_PEER_ADDRESS=localhost:7051

N_TX=${1:-50}
SEED=${2:-1}
OUTDIR=/mnt/d/fabric-d2/results/seed${SEED}
mkdir -p "$OUTDIR"
LOG="$OUTDIR/raw_${N_TX}tx.csv"
echo "tx_id,start_unix_ms,end_unix_ms,latency_ms,status" > "$LOG"

ORDERER_CAFILE="${PWD}/organizations/ordererOrganizations/example.com/orderers/orderer.example.com/msp/tlscacerts/tlsca.example.com-cert.pem"
PEER1_TLS="${PWD}/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt"
PEER2_TLS="${PWD}/organizations/peerOrganizations/org2.example.com/peers/peer0.org2.example.com/tls/ca.crt"

echo "=== Run: N_TX=$N_TX SEED=$SEED (sequential) ==="
T_OVERALL_START=$(date +%s%N)
OK_COUNT=0
FAIL_COUNT=0

for idx in $(seq 1 "$N_TX"); do
  asset_id="bench_s${SEED}_${idx}_$$"
  t_start_ns=$(date +%s%N)
  t_start_ms=$((t_start_ns / 1000000))
  if peer chaincode invoke \
      -o localhost:7050 \
      --ordererTLSHostnameOverride orderer.example.com \
      --tls --cafile "$ORDERER_CAFILE" \
      -C mychannel -n basic \
      --peerAddresses localhost:7051 --tlsRootCertFiles "$PEER1_TLS" \
      --peerAddresses localhost:9051 --tlsRootCertFiles "$PEER2_TLS" \
      -c "{\"function\":\"CreateAsset\",\"Args\":[\"${asset_id}\",\"red\",\"100\",\"alice\",\"42\"]}" \
      >/dev/null 2>&1; then
    t_end_ms=$(($(date +%s%N) / 1000000))
    echo "${idx},${t_start_ms},${t_end_ms},$((t_end_ms - t_start_ms)),OK" >> "$LOG"
    OK_COUNT=$((OK_COUNT + 1))
  else
    t_end_ms=$(($(date +%s%N) / 1000000))
    echo "${idx},${t_start_ms},${t_end_ms},$((t_end_ms - t_start_ms)),FAIL" >> "$LOG"
    FAIL_COUNT=$((FAIL_COUNT + 1))
  fi
done

T_OVERALL_END=$(date +%s%N)
DURATION_MS=$(( (T_OVERALL_END - T_OVERALL_START) / 1000000 ))
TPS=$(awk "BEGIN { printf \"%.2f\", $OK_COUNT / ($DURATION_MS / 1000.0) }")

echo ""
echo "Log: $LOG"
echo "Total wall-clock: ${DURATION_MS}ms ($(awk "BEGIN{printf \"%.1f\", $DURATION_MS/1000}") s)"
echo "Succeeded: $OK_COUNT / $N_TX"
echo "Failed:    $FAIL_COUNT"
echo "Throughput (sequential): $TPS tx/s"
echo ""
echo "Latency percentiles (ms):"
awk -F',' 'NR>1 && $5=="OK" { print $4 }' "$LOG" | sort -n | \
  awk -v n="$OK_COUNT" '
    { a[NR]=$1 }
    END {
      if (n==0) { print "  no successful tx"; exit }
      p50=a[int(n*0.50)+1]; p95=a[int(n*0.95)+1]; p99=a[int(n*0.99)+1]; max=a[n]
      mean=0
      for (i=1;i<=n;i++) mean+=a[i]; mean/=n
      printf "  p50=%d  p95=%d  p99=%d  max=%d  mean=%.1f\n", p50, p95, p99, max, mean
    }'
