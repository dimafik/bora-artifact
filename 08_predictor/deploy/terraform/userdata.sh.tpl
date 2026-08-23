#!/bin/bash
set -e
yum install -y docker
systemctl start docker

NODE_ID=${node_id}
REGION=${region}
IMAGE=${image_uri}
AI=${ai_augmented}

# Pull image
docker pull "$IMAGE"

# Determine peers from cluster discovery (Route53 or static)
# For simplicity, this template expects PEERS env var injected
# at deploy time (e.g., via Terraform locals + Route53 DNS lookup)

docker run -d \
  --name raft-node \
  --restart always \
  -p 6000:6000 \
  -e NODE_ID="$NODE_ID" \
  -e PORT=6000 \
  -e REGION="$REGION" \
  -e AI_AUGMENTED="$([ "$AI" = "true" ] && echo 1 || echo 0)" \
  "$IMAGE"

echo "Raft node $NODE_ID in $REGION started"
