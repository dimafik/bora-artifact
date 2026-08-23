#!/usr/bin/env bash
# Runs ON host1. Concurrent invoke load: PAR parallel submitters x EACH each.
PAR=${1:-8}; EACH=${2:-8}
PE1="-e CORE_PEER_ADDRESS=peer0.org1.example.com:7051 -e CORE_PEER_MSPCONFIGPATH=/etc/hyperledger/fabric/adminmsp"
INV="--orderer orderer.example.com:7050 --tls --cafile /tmp/ord-ca.crt --ordererTLSHostnameOverride orderer.example.com -C mychannel -n basic --peerAddresses peer0.org1.example.com:7051 --tlsRootCertFiles /tmp/org1-ca.crt --peerAddresses peer0.org2.example.com:7051 --tlsRootCertFiles /tmp/org2-ca.crt"
TAG=${3:-base}
start=$(date +%s.%N)
for p in $(seq 1 "$PAR"); do
  ( for k in $(seq 1 "$EACH"); do
      sudo docker exec $PE1 peer0 peer chaincode invoke $INV -c "{\"function\":\"CreateAsset\",\"Args\":[\"a_${TAG}_${p}_${k}\",\"b\",\"1\",\"x\",\"1\"]}" >/dev/null 2>&1
    done ) &
done
wait
end=$(date +%s.%N)
tot=$((PAR*EACH)); el=$(echo "$end - $start" | bc)
printf 'tx/s=%.2f total=%d elapsed=%.2fs par=%d\n' "$(echo "$tot/$el" | bc -l)" "$tot" "$el" "$PAR"
