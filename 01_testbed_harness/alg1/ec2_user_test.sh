#!/usr/bin/env bash
chmod 600 /tmp/bk.pem 2>/dev/null
IP=43.201.73.122
for u in ubuntu admin root fedora centos debian; do
  r=$(timeout 15 ssh -i /tmp/bk.pem -o StrictHostKeyChecking=no -o ConnectTimeout=10 -o BatchMode=yes "$u@$IP" 'echo OK; id -un; (docker --version 2>/dev/null||echo NO-DOCKER)' 2>&1 | tail -3)
  echo "[$u] $r"
done
