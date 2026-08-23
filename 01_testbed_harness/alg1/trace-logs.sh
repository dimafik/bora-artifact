#!/bin/bash
docker run -d --name pumba-trace -v /var/run/docker.sock:/var/run/docker.sock \
  gaiaadm/pumba:latest --interval 10m --log-level info \
  netem --tc-image gaiadocker/iproute2 --duration 60s \
  delay --time 200 orderer3.example.com 2>&1 | tail -1
sleep 8
echo "=== leader log forwarding events ==="
docker logs --tail 500 orderer.example.com 2>&1 | grep -iE 'forwarding|raft|leader|HasLeader|appendentries|tick' | tail -20
echo ""
echo "=== each orderer activity ==="
for o in orderer.example.com orderer2.example.com orderer3.example.com orderer4.example.com orderer5.example.com; do
  cnt=$(docker logs --since 30s "$o" 2>&1 | wc -l)
  err=$(docker logs --since 30s "$o" 2>&1 | grep -ciE 'fail|error|timeout|forwarding')
  echo "$o: log lines=$cnt, errs/timeouts=$err"
done
docker rm -f pumba-trace 2>&1 | tail -1
