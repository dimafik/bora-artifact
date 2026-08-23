#!/usr/bin/env bash
set -e
export GOROOT=$HOME/go-install
export PATH=$GOROOT/bin:/usr/bin:/bin
cd /tmp
cp /mnt/d/fabric-d2/alg1/bora_sidecar.go .
GOOS=linux CGO_ENABLED=0 go build -ldflags='-s -w' -o /tmp/bora-sidecar bora_sidecar.go
ls -lh /tmp/bora-sidecar
cp /tmp/bora-sidecar /mnt/d/fabric-d2/results/bora-sidecar.bin
echo "SIDECAR_BUILD_OK"
