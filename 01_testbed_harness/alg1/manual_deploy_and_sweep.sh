#!/usr/bin/env bash
# Deploy 'basic' chaincode WITHOUT network.sh (which needs jq, wiped on restart).
# Parse package-id with sed. Then run the below-ceiling sweep + ledger cross-check.
set -u
export PATH=/home/jinu337/go-install/bin:/mnt/d/fabric-d2/fabric-samples/bin-linux/bin:/usr/local/bin:/usr/bin:/bin
export GOPATH=/home/jinu337/go
export FABRIC_CFG_PATH=/mnt/d/fabric-d2/fabric-samples/config
export CORE_PEER_TLS_ENABLED=true
cd /mnt/d/fabric-d2/fabric-samples/test-network
TESTNET=$PWD
OUT=/mnt/d/fabric-d2/results/validate_manual_$(date +%Y%m%d-%H%M%S); mkdir -p "$OUT"
ORDERER_CA=$TESTNET/organizations/ordererOrganizations/example.com/orderers/orderer.example.com/msp/tlscacerts/tlsca.example.com-cert.pem
O1CA=$TESTNET/organizations/peerOrganizations/org1.example.com/peers/peer0.org1.example.com/tls/ca.crt
O2CA=$TESTNET/organizations/peerOrganizations/org2.example.com/peers/peer0.org2.example.com/tls/ca.crt
POLICY="OR('Org1MSP.peer','Org2MSP.peer')"

setOrg1(){ export CORE_PEER_LOCALMSPID=Org1MSP CORE_PEER_TLS_ROOTCERT_FILE=$O1CA CORE_PEER_MSPCONFIGPATH=$TESTNET/organizations/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp CORE_PEER_ADDRESS=localhost:7051; }
setOrg2(){ export CORE_PEER_LOCALMSPID=Org2MSP CORE_PEER_TLS_ROOTCERT_FILE=$O2CA CORE_PEER_MSPCONFIGPATH=$TESTNET/organizations/peerOrganizations/org2.example.com/users/Admin@org2.example.com/msp CORE_PEER_ADDRESS=localhost:9051; }

echo "=== vendor + package ==="
( cd ../asset-transfer-basic/chaincode-go && GO111MODULE=on go mod vendor ) 2>&1 | tail -1
rm -f basic.tar.gz
peer lifecycle chaincode package basic.tar.gz --path ../asset-transfer-basic/chaincode-go --lang golang --label basic_1.0 2>&1 | tail -2 || { echo PACKAGE_FAIL; exit 1; }

echo "=== install on both orgs ==="
setOrg1; peer lifecycle chaincode install basic.tar.gz 2>&1 | tail -1
setOrg2; peer lifecycle chaincode install basic.tar.gz 2>&1 | tail -1

setOrg1
PKGID=$(peer lifecycle chaincode queryinstalled 2>&1 | sed -n 's/^Package ID: \(basic_1.0:[a-f0-9]*\),.*/\1/p' | head -1)
echo "PKGID=$PKGID"
[ -z "$PKGID" ] && { echo NO_PKGID; exit 1; }

echo "=== approve (both orgs) ==="
setOrg1
peer lifecycle chaincode approveformyorg -o localhost:7050 --ordererTLSHostnameOverride orderer.example.com \
  --channelID mychannel --name basic --version 1.0 --package-id "$PKGID" --sequence 1 \
  --signature-policy "$POLICY" --tls --cafile "$ORDERER_CA" 2>&1 | tail -1
setOrg2
peer lifecycle chaincode approveformyorg -o localhost:7050 --ordererTLSHostnameOverride orderer.example.com \
  --channelID mychannel --name basic --version 1.0 --package-id "$PKGID" --sequence 1 \
  --signature-policy "$POLICY" --tls --cafile "$ORDERER_CA" 2>&1 | tail -1

echo "=== commit ==="
setOrg1
peer lifecycle chaincode commit -o localhost:7050 --ordererTLSHostnameOverride orderer.example.com \
  --channelID mychannel --name basic --version 1.0 --sequence 1 --signature-policy "$POLICY" \
  --tls --cafile "$ORDERER_CA" \
  --peerAddresses localhost:7051 --tlsRootCertFiles "$O1CA" \
  --peerAddresses localhost:9051 --tlsRootCertFiles "$O2CA" 2>&1 | tail -3

echo "=== committed? ==="
peer lifecycle chaincode querycommitted --channelID mychannel --name basic 2>&1 | head -5

geth(){ docker exec peer0.org1.example.com peer channel getinfo -c mychannel 2>/dev/null | grep -ao '"height":[0-9]*' | grep -ao '[0-9]*'; }
echo "ledger height after deploy = $(geth)"

echo "================ below-ceiling sweep (100-500 tps) ================"
H_BEFORE=$(geth); T_BEFORE=$(date +%s)
docker rm -f caliper-validate 2>/dev/null || true
docker run --rm --name caliper-validate --network fabric_test \
  -v "/mnt/d/fabric-d2/caliper-workspace:/hyperledger/caliper/workspace" \
  -v "$TESTNET/organizations:/cryptoMount" \
  --add-host=host.docker.internal:host-gateway \
  -e CALIPER_BIND_SUT=fabric:fabric-gateway \
  -e CALIPER_BENCHCONFIG=benchmarks/belowceiling-sweep.yaml \
  -e CALIPER_NETWORKCONFIG=networks/fabric-5node.yaml \
  -e CALIPER_FLOW_ONLY_TEST=true \
  -e CALIPER_REPORT_PATH=/hyperledger/caliper/workspace/report-validate.html \
  hyperledger/caliper:0.6.0 launch manager > "$OUT/caliper-validate.log" 2>&1
cp /mnt/d/fabric-d2/caliper-workspace/report-validate.html "$OUT/" 2>/dev/null || true
H_AFTER=$(geth); T_AFTER=$(date +%s)
echo "================ RESULT ================"
DH=$(( H_AFTER - H_BEFORE )); DT=$(( T_AFTER - T_BEFORE ))
echo "ledger height: $H_BEFORE -> $H_AFTER (Δ=$DH blocks / ${DT}s, ~$(( DT>0 ? DH*10/DT : 0 )) tx/s)"
echo "--- Caliper per-round Succ/Fail ---"
grep -aoiE "rate-[0-9]+ Round [0-9]+ Transaction Info\] - Submitted: [0-9]+ Succ: [0-9]+ Fail:[0-9]+" "$OUT/caliper-validate.log" 2>/dev/null | tail -8
echo "--- Caliper final summary (Name|Succ|Fail|SendRate|...|Throughput) ---"
grep -aE "\| rate-[0-9]+" "$OUT/caliper-validate.log" 2>/dev/null | head -6
echo "Results dir: $OUT"
echo "MANUAL_VALIDATE_DONE"
