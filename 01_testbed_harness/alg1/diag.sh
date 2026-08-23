#!/bin/bash
echo "=== clean RTT host->orderer3:10053 ==="
for i in 1 2 3; do
  python3 -c 'import socket,time; s=socket.socket(); s.settimeout(0.5); t=time.perf_counter(); s.connect(("localhost",10053)); print(f"{(time.perf_counter()-t)*1000:.2f}ms"); s.close()'
done

echo "=== inject 200ms on orderer3 ==="
docker run -d --name pumba-diag -v /var/run/docker.sock:/var/run/docker.sock \
  gaiaadm/pumba:latest --interval 10m --log-level info \
  netem --tc-image gaiadocker/iproute2 --duration 60s \
  delay --time 200 orderer3.example.com 2>&1 | tail -1
sleep 6

echo "=== attack RTT host->orderer3:10053 ==="
for i in 1 2 3; do
  python3 -c 'import socket,time; s=socket.socket(); s.settimeout(2); t=time.perf_counter(); s.connect(("localhost",10053)); print(f"{(time.perf_counter()-t)*1000:.2f}ms"); s.close()'
done

echo "=== inter-orderer RTT via docker exec ==="
docker exec orderer.example.com sh -c 'ls /etc/alpine-release 2>/dev/null && echo alpine || echo not_alpine'
docker exec orderer.example.com sh -c 'which nc 2>&1; nc -zvw2 orderer3.example.com 10050 2>&1; date' 2>&1 | tail -10
docker exec orderer.example.com sh -c 'getent hosts orderer3.example.com 2>&1; time nc -zw2 orderer3.example.com 10050 2>&1' 2>&1 | tail -10

docker rm -f pumba-diag 2>&1 | tail -1
