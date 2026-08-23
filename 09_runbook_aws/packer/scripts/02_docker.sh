#!/usr/bin/env bash
# 02_docker.sh — Docker 24.0.7 + docker-compose v2.23.3
set -euxo pipefail

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo \
    "deb [arch=amd64 signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu jammy stable" \
    > /etc/apt/sources.list.d/docker.list

apt-get update -y
apt-get install -y \
    docker-ce=5:24.0.7-1~ubuntu.22.04~jammy \
    docker-ce-cli=5:24.0.7-1~ubuntu.22.04~jammy \
    containerd.io \
    docker-buildx-plugin \
    docker-compose-plugin=2.23.3-1~ubuntu.22.04~jammy

usermod -aG docker ubuntu
systemctl enable docker

# Pre-pull Fabric images (network cost amortized into AMI build)
docker pull "hyperledger/fabric-orderer:${FABRIC_VERSION:-2.5.4}"
docker pull "hyperledger/fabric-peer:${FABRIC_VERSION:-2.5.4}"
docker pull "hyperledger/fabric-tools:${FABRIC_VERSION:-2.5.4}"
docker pull "hyperledger/fabric-ccenv:${FABRIC_VERSION:-2.5.4}"
docker pull "hyperledger/fabric-baseos:${FABRIC_VERSION:-2.5.4}"
