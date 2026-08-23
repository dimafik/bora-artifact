#!/usr/bin/env bash
set -e
export GOROOT=$HOME/go-install
export GOPATH=$HOME/gopath
export GOCACHE=$HOME/.gocache
export PATH=$GOROOT/bin:$PATH
mkdir -p $GOPATH $GOCACHE

cd $HOME/raft-advisor/fabric

echo "Building patched orderer with Go $(go version)"
go build -o /tmp/orderer-bora ./cmd/orderer
ls -lh /tmp/orderer-bora
echo "BUILD_OK"
