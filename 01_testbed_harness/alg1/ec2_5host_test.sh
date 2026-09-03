#!/usr/bin/env bash
# BORA_KEY is the EC2 private key for the five hosts; it is not in this
# repository and its path is not either.
cp "${BORA_KEY:?set BORA_KEY to your EC2 private key}" /tmp/bk.pem
chmod 600 /tmp/bk.pem
IPS=(43.201.73.122 54.180.99.165 43.201.25.172 54.180.117.221 15.164.226.99)
for ip in "${IPS[@]}"; do
  echo "=== $ip ==="
  timeout 18 ssh -i /tmp/bk.pem -o StrictHostKeyChecking=no -o ConnectTimeout=12 -o BatchMode=yes "ec2-user@$ip" \
    'echo OK; nproc; free -m | awk "/Mem/{print \"RAM_MB\", \$2}"; (docker --version 2>/dev/null || echo NO-DOCKER); (cloud-init status 2>/dev/null | head -1)' 2>&1 | tail -6
done
