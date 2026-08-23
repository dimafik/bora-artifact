#!/bin/sh
apk add --no-cache curl >/dev/null 2>&1
for p in 7050 7053 7055 8443 9443; do
  code=$(curl -s -m 2 -o /dev/null -w '%{http_code}' http://orderer3.example.com:$p/ 2>&1 || echo CURLFAIL)
  echo "orderer3:$p -> $code"
done
