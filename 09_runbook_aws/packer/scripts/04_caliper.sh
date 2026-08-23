#!/usr/bin/env bash
# 04_caliper.sh — Node.js 18 + Caliper 0.5.0 + Fabric Node SDK
set -euxo pipefail

CALIPER_VERSION=${CALIPER_VERSION:-0.5.0}

# Node.js 18.18.2 LTS
curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
apt-get install -y nodejs=18.18.2-1nodesource1

mkdir -p /opt/caliper
cd /opt/caliper

cat >package.json <<EOF
{
  "name": "sched-bft-caliper-driver",
  "version": "1.0.0",
  "private": true,
  "dependencies": {
    "@hyperledger/caliper-cli": "${CALIPER_VERSION}",
    "fabric-network": "2.2.20",
    "fabric-protos": "2.2.20",
    "fabric-common": "2.2.20"
  }
}
EOF

npm install --no-audit --no-fund
npx caliper bind --caliper-bind-sut fabric:2.4 --caliper-bind-args="-g"

chown -R ubuntu:ubuntu /opt/caliper
