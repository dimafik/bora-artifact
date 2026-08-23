#!/usr/bin/env bash
# Run PRISM on the BORA election DTMCs; save full output, then summarise.
set -u
SRC="/mnt/d/프랑스 업데이트/TNSE 스페셜이슈 논문/IS-Raft-LAC/formal/prism"
docker run --rm -v /tmp:/host ubuntu:24.04 rm -rf /host/prismwork 2>/dev/null
mkdir -p /tmp/prismwork
cp "$SRC"/*.pm "$SRC"/*.props /tmp/prismwork/
docker run --rm -v /tmp/prismwork:/work -v /tmp/prism-inst:/inst ubuntu:24.04 bash -c '
  apt-get update -qq >/dev/null 2>&1
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq default-jre-headless curl ca-certificates >/dev/null 2>&1
  if [ ! -x /inst/prism/bin/prism ]; then
    curl -sSL -o /tmp/prism.tgz https://www.prismmodelchecker.org/dl/prism-4.8.1-linux64-x86.tar.gz
    mkdir -p /inst && tar xzf /tmp/prism.tgz -C /inst
    D=$(find /inst -maxdepth 1 -type d -name "prism-*" | head -1); ln -sfn "$D" /inst/prism
    ( cd /inst/prism && ./install.sh >/dev/null 2>&1 ) || true
  fi
  P=/inst/prism/bin/prism
  cd /work
  "$P" -version > out.txt 2>&1
  for E in 3 4 5; do
    echo "##### W2 E=$E (election.props: P>=1[F el], P=?[F el], E[rounds]) #####" >> out.txt
    "$P" election.pm election.props -const NE=$E >> out.txt 2>&1
    echo "##### W3 E=$E (rounds.props) #####" >> out.txt
    "$P" election_w3.pm rounds.props -const NE=$E >> out.txt 2>&1
  done
  for K in 0 1 2 3 4 5 6 8 12 20; do
    echo "##### W2 E=5 Kmax=$K (pfel.props: P[leader within k rounds]) #####" >> out.txt
    "$P" election_k.pm pfel.props -const NE=5 -const Kmax=$K >> out.txt 2>&1
  done
  chmod 666 out.txt 2>/dev/null
'
cp /tmp/prismwork/out.txt /mnt/d/fabric-d2/alg1/prism_out.txt 2>/dev/null
echo "=== VERSION ==="; grep -aiE "PRISM version" /tmp/prismwork/out.txt | head -1
echo "=== RESULTS ==="; grep -aE "^#####|^Result" /tmp/prismwork/out.txt
echo "=== ERRORS ==="; grep -aiE "error|exception|deadlock|undefined" /tmp/prismwork/out.txt | grep -aviE "no deadlock|reward struct" | head
echo PRISM_DONE
