#!/usr/bin/env bash
# 01_base.sh -- base OS packages, chrony, Go, Python
# All package sources are Ubuntu apt + standard PyPI; no custom installer URLs.
set -euxo pipefail

export DEBIAN_FRONTEND=noninteractive
GO_VERSION=${GO_VERSION:-1.21.5}

apt-get update -y
apt-get upgrade -y
apt-get install -y --no-install-recommends \
    ca-certificates curl gnupg jq git \
    chrony python3 python3-pip python3-venv \
    build-essential unzip net-tools tcpdump \
    awscli

# chrony: aggressive sync for cross-VM clock alignment
cat >/etc/chrony/chrony.conf <<EOF
pool ntp.ubuntu.com iburst maxsources 4
makestep 1.0 3
rtcsync
driftfile /var/lib/chrony/drift
EOF
systemctl enable chrony

# Go from official source (Google domain) -- standard practice for go.dev
curl -fsSLO "https://go.dev/dl/go${GO_VERSION}.linux-amd64.tar.gz"
rm -rf /usr/local/go
tar -C /usr/local -xzf "go${GO_VERSION}.linux-amd64.tar.gz"
rm "go${GO_VERSION}.linux-amd64.tar.gz"
cat >/etc/profile.d/go.sh <<'EOF'
export PATH=$PATH:/usr/local/go/bin:/opt/fabric/bin
EOF
chmod +x /etc/profile.d/go.sh

# Python deps for BRAO sidecar -- standard PyPI index only.
# Note: torch from PyPI pulls a fat ~750 MB wheel (includes CUDA stubs).
# The BRAO predictor is small (~4 MB) so this is acceptable.
# If AMI size becomes an issue, install torch in Ansible instead of AMI.
pip3 install --no-cache-dir \
    "torch==2.1.2" \
    "fastapi==0.110.0" \
    "uvicorn==0.27.0" \
    "prometheus-client==0.20.0" \
    "numpy==1.26.3" \
    "scipy==1.12.0" \
    "pyarrow==15.0.0" \
    "pandas==2.2.0"
