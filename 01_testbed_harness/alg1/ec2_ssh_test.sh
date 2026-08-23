#!/usr/bin/env bash
cp ~/raft-cluster-key.pem /tmp/k.pem 2>/dev/null
ls -la ~/*.pem 2>/dev/null
chmod 600 /tmp/k.pem 2>/dev/null
IPS=(43.201.21.8 43.201.71.253)
for ip in "${IPS[@]}"; do
  echo "=== $ip ==="
  for u in ec2-user ubuntu; do
    r=$(timeout 15 ssh -i /tmp/k.pem -o StrictHostKeyChecking=no -o ConnectTimeout=10 -o BatchMode=yes "$u@$ip" "echo OK-$u; nproc; free -m | grep Mem; docker --version 2>/dev/null || echo no-docker" 2>&1 | tail -5)
    echo "[$u] $r"
  done
done
