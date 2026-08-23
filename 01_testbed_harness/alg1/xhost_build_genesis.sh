#!/usr/bin/env bash
# Build crypto + genesis for a 5-host Raft cluster where every orderer listens on
# port 7050 on its own host (cross-host). Orderer names resolve to private IPs via
# --add-host at run time, so the existing orderer*.example.com TLS SANs are valid.
set -e
export PATH=/mnt/d/fabric-d2/fabric-samples/bin-linux/bin:/usr/local/bin:/usr/bin:/bin
TN=/mnt/d/fabric-d2/fabric-samples/test-network
cd "$TN"
OUT=/mnt/d/fabric-d2/results/xhost; rm -rf "$OUT"; mkdir -p "$OUT"

echo "=== cryptogen (5 orderers + 2 orgs) ==="
rm -rf organizations/ordererOrganizations organizations/peerOrganizations
cryptogen generate --config=./organizations/cryptogen/crypto-config-orderer-5node.yaml --output=organizations 2>&1 | tail -1
cryptogen generate --config=./organizations/cryptogen/crypto-config-org1.yaml --output=organizations 2>&1 | tail -1
cryptogen generate --config=./organizations/cryptogen/crypto-config-org2.yaml --output=organizations 2>&1 | tail -1
echo "orderers: $(ls organizations/ordererOrganizations/example.com/orderers/ | wc -l)"

echo "=== configtx: all consenters -> port 7050 ==="
cp configtx/configtx-5node.yaml /tmp/ctx-xhost.yaml
# consenter Port lines 8050/10050/11050/12050 -> 7050
sed -i -E 's/Port: (8050|10050|11050|12050)/Port: 7050/' /tmp/ctx-xhost.yaml
# OrdererAddresses + any orderer*.example.com:PORT -> :7050
sed -i -E 's/(orderer[0-9]*\.example\.com):(8050|10050|11050|12050)/\1:7050/g' /tmp/ctx-xhost.yaml
echo "consenter ports after:"; grep -E "Port:" /tmp/ctx-xhost.yaml | sort | uniq -c
cp configtx/configtx.yaml /tmp/ctx.realbak 2>/dev/null || true
cp /tmp/ctx-xhost.yaml configtx/configtx.yaml

echo "=== genesis ==="
unset FABRIC_CFG_PATH
configtxgen -profile ChannelUsingRaft -outputBlock "$OUT/mychannel.block" -channelID mychannel -configPath ./configtx 2>&1 | grep -iE "writing|panic|error" | tail -2
cp /tmp/ctx.realbak configtx/configtx.yaml 2>/dev/null || true
[ -f "$OUT/mychannel.block" ] || { echo "GENESIS_FAIL"; exit 1; }
echo "genesis block: $(ls -la "$OUT/mychannel.block" | awk '{print $5}') bytes"

echo "=== stage per-orderer material into $OUT ==="
OD=organizations/ordererOrganizations/example.com/orderers
for i in 1 2 3 4 5; do
  h=orderer; [ "$i" -gt 1 ] && h="orderer$i"
  d="$OUT/$h"; mkdir -p "$d"
  cp -r "$OD/$h.example.com/msp" "$d/msp"
  cp -r "$OD/$h.example.com/tls" "$d/tls"
done
# the orderer org TLS CA (for osnadmin --ca-file)
cp "$OD/orderer.example.com/msp/tlscacerts/tlsca.example.com-cert.pem" "$OUT/orderer-ca.pem"
cp /mnt/d/fabric-d2/results/orderer-bora-v4.bin "$OUT/orderer-bora-v4.bin"
cp /mnt/d/fabric-d2/results/bora-sidecar-v3.bin "$OUT/bora-sidecar-v3.bin"
echo "XHOST_GENESIS_DONE staged $(ls "$OUT" | tr '\n' ' ')"
