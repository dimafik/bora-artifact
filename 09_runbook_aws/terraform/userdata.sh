#!/bin/bash
# Cloud-init bootstrap: identify role + start chrony + ready for Ansible
set -euo pipefail

ROLE="${role}"
ORG="${org}"
RUN_ID="${run_id}"
BUCKET="${bucket}"

cat >/etc/sched-bft.env <<EOF
ROLE=$ROLE
ORG=$ORG
RUN_ID=$RUN_ID
BUCKET=$BUCKET
EOF

# Clock sync — critical for tx timestamp alignment
systemctl enable --now chrony
chronyc -a 'burst 4/4'
chronyc -a makestep

# Set hostname for log clarity
hostnamectl set-hostname "sched-bft-$ROLE-$ORG"

# Prepare data dir
mkdir -p /data/{caliper,prom,probes,logs}
chown -R ubuntu:ubuntu /data

# Tag instance ready for Ansible
echo "READY" > /var/run/sched-bft-ready
