#!/usr/bin/env bash
set -e
export GOROOT=$HOME/go-install
export GOPATH=$HOME/gopath
export GOCACHE=$HOME/.gocache
export PATH=$GOROOT/bin:/usr/local/bin:/usr/bin:/bin
mkdir -p "$GOPATH" "$GOCACHE"
cd "$HOME/raft-advisor/fabric-v3.1.4"
echo "go: $(go version)"
echo "building patched orderer v4 (vote-reject)..."
go build -o /mnt/d/fabric-d2/results/orderer-bora-v4.bin ./cmd/orderer
ls -lh /mnt/d/fabric-d2/results/orderer-bora-v4.bin
echo "BUILD_V4_OK"
