#!/usr/bin/env bash
# Approve + commit 'basic' with an OR signature policy on the cross-host network.
#
# WHY A FILE AND NOT AN SSH ONE-LINER.  `--signature-policy OR('A','B')` passed
# through `ssh host "..."` is parsed twice: once locally, once by the remote
# shell, and the second pass sees a bare `(` and dies with
#   bash: -c: line 1: syntax error near unexpected token `('
# xhost_cc3.sh hits this, and xhost_commit.sh worked around it by dropping the
# policy and taking the DEFAULT majority-of-orgs one instead. That default is
# what makes caliper's service discovery need anchor peers in both orgs. Writing
# the command into a file on the host and running the file parses it once, so
# the OR policy survives and a single organisation can endorse.
#
# Usage: xhost_cc_or.sh
set -u
KEY=/tmp/bk.pem; chmod 600 "$KEY" 2>/dev/null
SSH="ssh -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=25 -o BatchMode=yes"
H1=43.201.32.112
H2=43.200.5.112
PKG="${1:-}"

if [ -z "$PKG" ]; then
  PKG=$($SSH ubuntu@$H1 'sudo docker exec -e CORE_PEER_ADDRESS=peer0.org1.example.com:7051 -e CORE_PEER_MSPCONFIGPATH=/etc/hyperledger/fabric/adminmsp peer0 peer lifecycle chaincode queryinstalled 2>/dev/null | grep -oE "basic_1:[a-f0-9]+" | head -1')
fi
[ -z "$PKG" ] && { echo "NO_PKGID_ABORT"; exit 1; }
echo "package-id: $PKG"

gen_remote(){   # $1 = org number, writes /tmp/cc_step.sh content on stdout
  cat <<REMOTE
set -u
PE="-e CORE_PEER_ADDRESS=peer0.org$1.example.com:7051 -e CORE_PEER_MSPCONFIGPATH=/etc/hyperledger/fabric/adminmsp"
ORDF="--orderer orderer.example.com:7050 --tls --cafile /tmp/ord-ca.crt --ordererTLSHostnameOverride orderer.example.com"
SP="--signature-policy"
POL="OR('Org1MSP.member','Org2MSP.member')"
sudo docker exec \$PE peer0 peer lifecycle chaincode approveformyorg \$ORDF \\
  --channelID mychannel --name basic --version 1.0 --package-id $PKG \\
  --sequence 1 \$SP "\$POL" 2>&1 | grep -aiE "committed|successfully|error|failed" | tail -2
REMOTE
}

echo "=== approve Org1 ==="
gen_remote 1 > /tmp/cc_o1.sh
$SSH ubuntu@$H1 'cat > /tmp/cc_step.sh' < /tmp/cc_o1.sh
$SSH ubuntu@$H1 'bash /tmp/cc_step.sh'

echo "=== approve Org2 ==="
gen_remote 2 > /tmp/cc_o2.sh
$SSH ubuntu@$H2 'cat > /tmp/cc_step.sh' < /tmp/cc_o2.sh
$SSH ubuntu@$H2 'bash /tmp/cc_step.sh'

echo "=== checkcommitreadiness ==="
cat > /tmp/cc_ready.sh <<'REMOTE'
set -u
PE="-e CORE_PEER_ADDRESS=peer0.org1.example.com:7051 -e CORE_PEER_MSPCONFIGPATH=/etc/hyperledger/fabric/adminmsp"
POL="OR('Org1MSP.member','Org2MSP.member')"
sudo docker exec $PE peer0 peer lifecycle chaincode checkcommitreadiness \
  --channelID mychannel --name basic --version 1.0 --sequence 1 \
  --signature-policy "$POL" 2>&1 | grep -aiE "Org[12]MSP|error" | tail -3
REMOTE
$SSH ubuntu@$H1 'cat > /tmp/cc_step.sh' < /tmp/cc_ready.sh
$SSH ubuntu@$H1 'bash /tmp/cc_step.sh'

echo "=== commit (lifecycle policy is majority, so both peers endorse) ==="
cat > /tmp/cc_commit.sh <<'REMOTE'
set -u
PE="-e CORE_PEER_ADDRESS=peer0.org1.example.com:7051 -e CORE_PEER_MSPCONFIGPATH=/etc/hyperledger/fabric/adminmsp"
ORDF="--orderer orderer.example.com:7050 --tls --cafile /tmp/ord-ca.crt --ordererTLSHostnameOverride orderer.example.com"
POL="OR('Org1MSP.member','Org2MSP.member')"
sudo docker exec $PE peer0 peer lifecycle chaincode commit $ORDF \
  --channelID mychannel --name basic --version 1.0 --sequence 1 \
  --signature-policy "$POL" \
  --peerAddresses peer0.org1.example.com:7051 --tlsRootCertFiles /tmp/org1-ca.crt \
  --peerAddresses peer0.org2.example.com:7051 --tlsRootCertFiles /tmp/org2-ca.crt \
  2>&1 | grep -aiE "committed|successfully|error|failed" | tail -2
REMOTE
$SSH ubuntu@$H1 'cat > /tmp/cc_step.sh' < /tmp/cc_commit.sh
$SSH ubuntu@$H1 'bash /tmp/cc_step.sh'

sleep 4
echo "=== querycommitted ==="
$SSH ubuntu@$H1 'sudo docker exec -e CORE_PEER_ADDRESS=peer0.org1.example.com:7051 -e CORE_PEER_MSPCONFIGPATH=/etc/hyperledger/fabric/adminmsp peer0 peer lifecycle chaincode querycommitted --channelID mychannel --name basic 2>&1 | grep -aiE "Version|Endorsement|Approvals|error" | tail -3'
echo "XHOST_CC_OR_DONE"
