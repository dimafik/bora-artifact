#!/usr/bin/env bash
pkill -9 ssh 2>/dev/null
sleep 3
cp /mnt/c/Users/jinu3/Bora_key1.pem /tmp/bk.pem 2>/dev/null
chmod 600 /tmp/bk.pem
echo "lingering ssh: $(pgrep -c ssh)"
echo "=== fresh SSH to each host (15s timeout) ==="
for ip in 15.164.215.28 13.209.97.224 13.209.3.44 54.180.145.47 52.78.184.161; do
  r=$(timeout 25 ssh -i /tmp/bk.pem -o StrictHostKeyChecking=no -o BatchMode=yes -o ConnectTimeout=15 -o ServerAliveInterval=5 "ubuntu@$ip" 'sudo docker inspect -f "{{.State.Status}}" orderer 2>/dev/null' 2>&1 | tail -1)
  echo "  $ip orderer=${r:-TIMEOUT/UNREACHABLE}"
done
echo "SSH_PROBE_DONE"
