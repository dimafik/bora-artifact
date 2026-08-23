#!/usr/bin/env bash
# Install Docker on all 5 BORA hosts (Ubuntu), in parallel.
chmod 600 /tmp/bk.pem 2>/dev/null
PUB=(43.201.73.122 54.180.99.165 43.201.25.172 54.180.117.221 15.164.226.99)
SSH="ssh -i /tmp/bk.pem -o StrictHostKeyChecking=no -o ConnectTimeout=15 -o BatchMode=yes"
install_one(){
  local ip=$1
  $SSH ubuntu@$ip 'sudo apt-get update -y >/tmp/apt.log 2>&1; sudo DEBIAN_FRONTEND=noninteractive apt-get install -y docker.io >>/tmp/apt.log 2>&1; sudo usermod -aG docker ubuntu; sudo systemctl enable --now docker; echo "[$(hostname -I | awk "{print \$1}")] docker=$(sudo docker --version 2>/dev/null)"' 2>&1 | tail -1
}
for ip in "${PUB[@]}"; do install_one "$ip" & done
wait
echo "DOCKER_INSTALL_DONE"
