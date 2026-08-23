#!/usr/bin/env bash
# 05_observability.sh — Prometheus 2.48.0 + node_exporter
set -euxo pipefail

PROM_VERSION=2.48.0
NODE_EXP_VERSION=1.7.0

# Prometheus
cd /tmp
curl -fsSLO "https://github.com/prometheus/prometheus/releases/download/v${PROM_VERSION}/prometheus-${PROM_VERSION}.linux-amd64.tar.gz"
tar -xzf "prometheus-${PROM_VERSION}.linux-amd64.tar.gz"
mv "prometheus-${PROM_VERSION}.linux-amd64" /opt/prometheus
rm "prometheus-${PROM_VERSION}.linux-amd64.tar.gz"

# node_exporter
curl -fsSLO "https://github.com/prometheus/node_exporter/releases/download/v${NODE_EXP_VERSION}/node_exporter-${NODE_EXP_VERSION}.linux-amd64.tar.gz"
tar -xzf "node_exporter-${NODE_EXP_VERSION}.linux-amd64.tar.gz"
install -m 0755 "node_exporter-${NODE_EXP_VERSION}.linux-amd64/node_exporter" /usr/local/bin/
rm -rf "node_exporter-${NODE_EXP_VERSION}.linux-amd64" "node_exporter-${NODE_EXP_VERSION}.linux-amd64.tar.gz"

# Prometheus systemd unit
cat >/etc/systemd/system/prometheus.service <<'EOF'
[Unit]
Description=Prometheus
After=network.target

[Service]
ExecStart=/opt/prometheus/prometheus \
    --config.file=/opt/prometheus/prometheus.yml \
    --storage.tsdb.path=/data/prom/tsdb \
    --storage.tsdb.retention.time=24h \
    --web.enable-lifecycle
Restart=always
User=ubuntu

[Install]
WantedBy=multi-user.target
EOF

# node_exporter systemd unit
cat >/etc/systemd/system/node_exporter.service <<'EOF'
[Unit]
Description=Prometheus node_exporter
After=network.target

[Service]
ExecStart=/usr/local/bin/node_exporter --web.listen-address=:9100
Restart=always
User=ubuntu

[Install]
WantedBy=multi-user.target
EOF

systemctl enable prometheus node_exporter
