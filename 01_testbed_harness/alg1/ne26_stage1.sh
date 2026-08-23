#!/usr/bin/env bash
set -e
GOROOT=$HOME/go-install
GOBIN=$GOROOT/bin/go
export PATH=$GOROOT/bin:$HOME/go/bin:$PATH

echo "[1/3] Installing Go 1.21 to $GOROOT (no sudo)..."
if ! $GOBIN version >/dev/null 2>&1; then
  cd /tmp
  if [ ! -f go1.21.5.linux-amd64.tar.gz ]; then
    wget -q https://go.dev/dl/go1.21.5.linux-amd64.tar.gz
  fi
  rm -rf $GOROOT
  mkdir -p $GOROOT
  tar -C $HOME -xzf go1.21.5.linux-amd64.tar.gz
  mv $HOME/go $GOROOT.tmp
  mv $GOROOT.tmp $GOROOT
fi
$GOBIN version

echo "[2/3] Cloning Fabric v2.5.10..."
WS=$HOME/raft-advisor
mkdir -p $WS
if [ ! -d $WS/fabric ]; then
  git clone --depth 1 --branch v2.5.10 https://github.com/hyperledger/fabric.git $WS/fabric
else
  echo "Fabric already cloned at $WS/fabric"
fi

echo "[3/3] Verifying patch target..."
ls -l $WS/fabric/orderer/consensus/etcdraft/chain.go | awk '{print $9, $5"B"}'
echo "NE26_STAGE1_READY"
