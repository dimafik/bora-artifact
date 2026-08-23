#!/usr/bin/env sh
apk add --no-cache nmap-ncat >/dev/null 2>&1
for port in 7050 7053 7445 9443 8443; do
  if nc -zv -w 2 orderer3.example.com $port 2>&1 | head -1 | grep -q "succeeded\|open"; then
    echo "orderer3:$port OPEN"
  else
    echo "orderer3:$port CLOSED"
  fi
done
