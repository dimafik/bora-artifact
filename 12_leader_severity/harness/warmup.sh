#!/usr/bin/env bash
# Warm-up guard for the R25C campaign.
#
# A peer launches its chaincode container lazily, on the first endorsement it is
# asked for. If the container is down, that first request fails and so does
# every transaction in the same window -- which is exactly how run 1 died
# ("ledger delta=0"), and almost certainly how r25b_20260810-233024 died too.
# A read-only query is enough to start the container, and it commits nothing.
set -u

query_peer(){
  local PC="$1" MSPID="$2"
  docker exec -e CORE_PEER_LOCALMSPID="$MSPID" -e CORE_PEER_MSPCONFIGPATH=/tmp/adminmsp \
    "$PC" peer chaincode query -C mychannel -n basic \
    -c '{"Args":["GetAllAssets"]}' >/dev/null 2>&1
}

echo "### chaincode 컨테이너 기동 전"
docker ps --filter "name=dev-peer" --format '  {{.Names}}  {{.Status}}'

echo
echo "### 워밍업 질의 (읽기 전용, 커밋 없음)"
for spec in "peer0.org1.example.com Org1MSP" "peer0.org2.example.com Org2MSP"; do
  set -- $spec
  if query_peer "$1" "$2"; then echo "  $1  응답 OK"; else echo "  $1  1차 실패 (기동 대기)"; fi
done

echo "  컨테이너 기동 대기 20s..."
sleep 20

echo
echo "### 재질의 (둘 다 성공해야 승인 정족수를 채울 수 있다)"
ok=0
for spec in "peer0.org1.example.com Org1MSP" "peer0.org2.example.com Org2MSP"; do
  set -- $spec
  if query_peer "$1" "$2"; then echo "  $1  응답 OK"; ok=$((ok+1)); else echo "  $1  여전히 실패"; fi
done

echo
echo "### chaincode 컨테이너 기동 후"
docker ps --filter "name=dev-peer" --format '  {{.Names}}  {{.Status}}'

echo
if [ "$ok" -eq 2 ]; then
  echo "WARMUP_OK  두 peer 모두 승인 가능 — 측정 시작해도 됨"
  exit 0
else
  echo "WARMUP_FAIL  ${ok}/2 peer만 응답 — 측정하면 안 됨"
  exit 1
fi
