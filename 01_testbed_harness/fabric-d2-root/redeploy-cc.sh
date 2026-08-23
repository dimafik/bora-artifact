#!/bin/bash
set -e
cd /mnt/d/fabric-d2/fabric-samples/test-network
export PATH=/tmp/bin:/tmp/go-install/go/bin:/mnt/d/fabric-d2/fabric-samples/bin-linux/bin:/usr/local/bin:/usr/bin:/bin
export FABRIC_CFG_PATH=/mnt/d/fabric-d2/fabric-samples/config
export GOPATH=/tmp/gopath
./network.sh deployCC \
  -ccn basic \
  -ccp ../asset-transfer-basic/chaincode-go \
  -ccl go \
  -ccep "OR('Org1MSP.peer','Org2MSP.peer')" \
  2>&1 | tail -10
