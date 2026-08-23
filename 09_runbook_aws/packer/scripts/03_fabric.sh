#!/usr/bin/env bash
# 03_fabric.sh — Fabric 2.5.4 binaries + config templates
set -euxo pipefail

FABRIC_VERSION=${FABRIC_VERSION:-2.5.4}

mkdir -p /opt/fabric /opt/fabric/bin /opt/fabric/config /opt/fabric/chaincodes
cd /tmp

curl -fsSLO "https://github.com/hyperledger/fabric/releases/download/v${FABRIC_VERSION}/hyperledger-fabric-linux-amd64-${FABRIC_VERSION}.tar.gz"
tar -xzf "hyperledger-fabric-linux-amd64-${FABRIC_VERSION}.tar.gz"
mv bin/* /opt/fabric/bin/
mv config/* /opt/fabric/config/
rm -rf bin config "hyperledger-fabric-linux-amd64-${FABRIC_VERSION}.tar.gz"

# Verify binaries
/opt/fabric/bin/orderer version
/opt/fabric/bin/peer version
/opt/fabric/bin/cryptogen version
/opt/fabric/bin/configtxgen version

chown -R ubuntu:ubuntu /opt/fabric
