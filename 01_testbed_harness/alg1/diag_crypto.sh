#!/usr/bin/env bash
cd /mnt/d/fabric-d2/fabric-samples/test-network
OD=organizations/ordererOrganizations/example.com
echo "=== orderer org CA dirs ==="
ls -la --time-style=+%H:%M:%S "$OD/tlsca/" 2>&1 | head
echo "=== per-orderer tls/ca.crt fingerprints ==="
for i in 1 2 3 4 5 6 7; do
  h=orderer
  if [ "$i" -gt 1 ]; then h="orderer$i"; fi
  f="$OD/orderers/$h.example.com/tls/ca.crt"
  if [ -f "$f" ]; then
    fp=$(openssl x509 -in "$f" -noout -fingerprint -sha256 2>/dev/null | cut -d= -f2 | cut -c1-23)
    sv=$(openssl x509 -in "$f" -noout -serial 2>/dev/null)
    echo "orderer$i ca.crt fp=$fp $sv"
  else
    echo "orderer$i ca.crt: MISSING ($f)"
  fi
done
echo "=== tlsca authoritative cert ==="
T="$OD/tlsca/tlsca.example.com-cert.pem"
if [ -f "$T" ]; then
  openssl x509 -in "$T" -noout -fingerprint -sha256 2>/dev/null | cut -d= -f2 | cut -c1-23
else
  echo "tlsca cert MISSING at $T"
  ls "$OD/tlsca/" 2>&1
fi
echo "=== what cert is orderer2 PRESENTING on the wire (live) ==="
echo | openssl s_client -connect localhost:8050 -servername orderer2.example.com 2>/dev/null | openssl x509 -noout -issuer -subject 2>/dev/null
echo "=== orderer1 presenting (live) ==="
echo | openssl s_client -connect localhost:7050 -servername orderer.example.com 2>/dev/null | openssl x509 -noout -issuer -subject 2>/dev/null
