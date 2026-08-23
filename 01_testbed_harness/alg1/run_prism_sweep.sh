#!/usr/bin/env bash
# PRISM sweep: P[leader within k rounds] for NE=3,4,5 across Kmax, for the G1 plot.
set -u
SRC="/mnt/d/프랑스 업데이트/TNSE 스페셜이슈 논문/IS-Raft-LAC/formal/prism"
docker run --rm -v /tmp:/host ubuntu:24.04 rm -rf /host/prismsw 2>/dev/null
mkdir -p /tmp/prismsw
cp "$SRC"/election_k.pm "$SRC"/pfel.props /tmp/prismsw/
docker run --rm -v /tmp/prismsw:/work -v /tmp/prism-inst:/inst ubuntu:24.04 bash -c '
  apt-get update -qq >/dev/null 2>&1
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq default-jre-headless >/dev/null 2>&1
  P=/inst/prism/bin/prism
  cd /work
  : > sweep.txt
  for NE in 3 4 5; do
    for K in 1 2 3 4 5 6 7 8 10 12 14; do
      R=$("$P" election_k.pm pfel.props -const NE=$NE -const Kmax=$K 2>&1 | grep -aE "^Result" | head -1 | grep -aoE "[0-9]+\.[0-9]+")
      echo "NE=$NE K=$K P=$R" >> sweep.txt
    done
  done
  cat sweep.txt
'
cp /tmp/prismsw/sweep.txt /mnt/d/fabric-d2/alg1/prism_sweep.txt 2>/dev/null
echo SWEEP_DONE
