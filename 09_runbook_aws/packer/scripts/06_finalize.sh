#!/usr/bin/env bash
# 06_finalize.sh — cleanup, lock versions, snapshot manifest
set -euxo pipefail

# Lock package versions
apt-mark hold docker-ce docker-ce-cli containerd.io \
    docker-compose-plugin nodejs

# Emit version manifest
mkdir -p /opt/sched-bft
cat >/opt/sched-bft/ami-manifest.txt <<EOF
Built:     $(date -Iseconds)
OS:        $(lsb_release -ds)
Kernel:    $(uname -r)
Docker:    $(docker --version)
Compose:   $(docker compose version --short)
Go:        $(/usr/local/go/bin/go version)
Node:      $(node --version)
NPM:       $(npm --version)
Python:    $(python3 --version)
Fabric:    $(/opt/fabric/bin/peer version | head -3 | tail -1)
Caliper:   $(cd /opt/caliper && npx caliper --version)
Prometheus: $(/opt/prometheus/prometheus --version 2>&1 | head -1)
EOF
cat /opt/sched-bft/ami-manifest.txt

# Clean apt cache to shrink AMI
apt-get clean
rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Zero unused blocks for smaller AMI snapshot (optional, slow but ~30% smaller)
# dd if=/dev/zero of=/EMPTY bs=1M || true; rm -f /EMPTY

sync
