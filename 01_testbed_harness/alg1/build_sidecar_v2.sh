#!/usr/bin/env bash
set -e
export GOROOT=$HOME/go-install
export PATH=$GOROOT/bin:/usr/bin:/bin
cd /tmp
cp /mnt/d/fabric-d2/alg1/bora_sidecar_v2.go .
GOOS=linux CGO_ENABLED=0 go build -ldflags='-s -w' -o /tmp/bora-sidecar-v2 bora_sidecar_v2.go
ls -lh /tmp/bora-sidecar-v2
cp /tmp/bora-sidecar-v2 /mnt/d/fabric-d2/results/bora-sidecar-v2.bin
echo "SIDECAR_V2_BUILD_OK"
