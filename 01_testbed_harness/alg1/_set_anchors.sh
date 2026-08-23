#!/usr/bin/env bash
# Set anchor peers for Org1 and Org2 on mychannel.
#
# WHY. The caliper network config uses `discover: true`. Service discovery can
# only find another organisation's endorsers if that organisation has an anchor
# peer recorded in the channel config. nsweep_bringup.sh joins the ORDERERS to
# the channel and never sets anchors, because leadership experiments do not
# endorse anything. Without them caliper reports
#   "no combination of peers can be derived which satisfy the endorsement policy"
# while a direct invoke with explicit --peerAddresses succeeds, which is exactly
# the split we observed.
set -u
TN=/mnt/d/fabric-d2/fabric-samples/test-network
cd "$TN" || exit 1
export PATH=/mnt/d/fabric-d2/fabric-samples/bin-linux/bin:$PATH
export FABRIC_CFG_PATH="$TN/../config"

for spec in "1 Org1MSP org1.example.com 7051" "2 Org2MSP org2.example.com 9051"; do
  set -- $spec
  ORG=$1; MSPID=$2; DOM=$3; PORT=$4
  export CORE_PEER_TLS_ENABLED=true
  export CORE_PEER_LOCALMSPID=$MSPID
  export CORE_PEER_TLS_ROOTCERT_FILE=$TN/organizations/peerOrganizations/$DOM/peers/peer0.$DOM/tls/ca.crt
  export CORE_PEER_MSPCONFIGPATH=$TN/organizations/peerOrganizations/$DOM/users/Admin@$DOM/msp
  export CORE_PEER_ADDRESS=localhost:$PORT

  peer channel fetch config /tmp/cfg_$ORG.pb -o localhost:7050 \
    --ordererTLSHostnameOverride orderer.example.com -c mychannel --tls \
    --cafile "$TN/organizations/ordererOrganizations/example.com/tlsca/tlsca.example.com-cert.pem" \
    >/dev/null 2>&1 || { echo "FETCH_FAIL org$ORG"; exit 1; }

  configtxlator proto_decode --input /tmp/cfg_$ORG.pb --type common.Block \
    --output /tmp/cfg_$ORG.json >/dev/null 2>&1
  jq '.data.data[0].payload.data.config' /tmp/cfg_$ORG.json > /tmp/conf_$ORG.json

  if jq -e --arg m "$MSPID" '.channel_group.groups.Application.groups[$m].values.AnchorPeers' \
       /tmp/conf_$ORG.json >/dev/null 2>&1; then
    echo "ALREADY_SET org$ORG"; continue
  fi

  jq --arg m "$MSPID" --arg h "peer0.$DOM" --argjson p "$PORT" \
    '.channel_group.groups.Application.groups[$m].values += {"AnchorPeers":{"mod_policy":"Admins","value":{"anchor_peers":[{"host":$h,"port":$p}]},"version":"0"}}' \
    /tmp/conf_$ORG.json > /tmp/conf_mod_$ORG.json

  configtxlator proto_encode --input /tmp/conf_$ORG.json --type common.Config --output /tmp/o_$ORG.pb >/dev/null 2>&1
  configtxlator proto_encode --input /tmp/conf_mod_$ORG.json --type common.Config --output /tmp/m_$ORG.pb >/dev/null 2>&1
  configtxlator compute_update --channel_id mychannel --original /tmp/o_$ORG.pb \
    --updated /tmp/m_$ORG.pb --output /tmp/upd_$ORG.pb >/dev/null 2>&1 \
    || { echo "COMPUTE_FAIL org$ORG"; exit 1; }
  configtxlator proto_decode --input /tmp/upd_$ORG.pb --type common.ConfigUpdate --output /tmp/upd_$ORG.json >/dev/null 2>&1
  echo '{"payload":{"header":{"channel_header":{"channel_id":"mychannel","type":2}},"data":{"config_update":'"$(cat /tmp/upd_$ORG.json)"'}}}' \
    | jq . > /tmp/env_$ORG.json
  configtxlator proto_encode --input /tmp/env_$ORG.json --type common.Envelope --output /tmp/env_$ORG.pb >/dev/null 2>&1

  peer channel update -f /tmp/env_$ORG.pb -c mychannel -o localhost:7050 \
    --ordererTLSHostnameOverride orderer.example.com --tls \
    --cafile "$TN/organizations/ordererOrganizations/example.com/tlsca/tlsca.example.com-cert.pem" \
    >/tmp/upd_$ORG.log 2>&1 \
    && echo "ANCHOR_OK org$ORG" || { echo "UPDATE_FAIL org$ORG"; tail -2 /tmp/upd_$ORG.log; }
done
