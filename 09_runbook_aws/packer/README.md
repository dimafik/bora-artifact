# Packer — Pre-baked Fabric AMI

Build once, reuse for every run. Costs ~$0.05 (t3.large × 25min build time).

## Prerequisites

```
packer >= 1.10.0
AWS CLI configured with EC2 + S3 permissions
```

## Build

```bash
cd packer/
packer init .
packer build fabric-ami.pkr.hcl
```

Output: `manifest.json` contains the AMI id. Copy to `../terraform/secrets.tfvars`:

```hcl
fabric_ami_id = "ami-0abc123def456"
```

## Verify

After build, launch the AMI manually, SSH, and run:

```bash
cat /opt/sched-bft/ami-manifest.txt
```

Expected manifest:

```
Built:      2026-XX-XXTHH:MM:SSZ
OS:         Ubuntu 22.04.X LTS
Docker:     Docker version 24.0.7
Compose:    2.23.3
Go:         go version go1.21.5 linux/amd64
Node:       v18.18.2
NPM:        9.8.1
Python:     Python 3.10.X
Fabric:     Version: 2.5.4
Caliper:    @hyperledger/caliper-cli: 0.5.0
Prometheus: prometheus, version 2.48.0
```

## What's pre-installed

- Ubuntu 22.04 LTS + chrony NTP sync
- Docker 24.0.7 + docker-compose 2.23.3
- Fabric 2.5.4 binaries: orderer, peer, cryptogen, configtxgen, fabric-ca-client
- Fabric 2.5.4 Docker images: orderer, peer, tools, ccenv, baseos (pre-pulled)
- Go 1.21.5
- Node.js 18.18.2 + npm 9.8.1
- Caliper 0.5.0 + Fabric Node SDK 2.2.20 (pre-bound)
- Prometheus 2.48.0 + node_exporter 1.7.0 (systemd-enabled)
- Python 3.10 + PyTorch 2.1.2 (CPU) + FastAPI for BRAO sidecar

## Why pre-bake

Installing all of the above at experiment-start time costs:
- ~35 min wall time × 5 VMs in parallel = 35 min
- 12% of the 5-hour budget burned before any tx flows

With pre-bake, T+0:00 → T+0:10 provisioning includes only EC2 instance launch
(cloud-init verifies the ready marker created by `userdata.sh`).
