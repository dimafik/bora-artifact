#!/usr/bin/env bash
cp "/mnt/c/Users/jinu3/Bora_key1.pem" /tmp/bk.pem 2>/dev/null
chmod 600 /tmp/bk.pem
IPS=(43.201.73.122 54.180.99.165 43.201.25.172 54.180.117.221 15.164.226.99)
for ip in "${IPS[@]}"; do
  echo "=== $ip ==="
  timeout 18 ssh -i /tmp/bk.pem -o StrictHostKeyChecking=no -o ConnectTimeout=12 -o BatchMode=yes "ec2-user@$ip" \
    'echo OK; nproc; free -m | awk "/Mem/{print \"RAM_MB\", \$2}"; (docker --version 2>/dev/null || echo NO-DOCKER); (cloud-init status 2>/dev/null | head -1)' 2>&1 | tail -6
done
