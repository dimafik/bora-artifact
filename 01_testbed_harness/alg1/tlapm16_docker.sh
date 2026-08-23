#!/usr/bin/env bash
# Run tlapm 1.6.0-pre in ubuntu:24.04 + Z3. Clean root-owned cache via a root container first.
set -u
SRC="/mnt/d/프랑스 업데이트/TNSE 스페셜이슈 논문/IS-Raft-LAC/formal/tla"
# 1) wipe /tmp/tla as root (prior runs left root-owned files)
docker run --rm -v /tmp:/host ubuntu:24.04 rm -rf /host/tla
mkdir -p /tmp/tla
cp "$SRC"/BORA.tla "$SRC"/Vanilla.tla "$SRC"/Liveness.tla "$SRC"/BORA_proof.tla /tmp/tla/
echo "=== files copied ==="; ls /tmp/tla
docker run --rm -v /tmp/tlapm16:/tlapm -v /tmp/tla:/work ubuntu:24.04 bash -c '
  apt-get update -qq >/dev/null 2>&1
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq z3 >/dev/null 2>&1
  cd /work
  rm -rf .tlacache
  timeout 1800 /tlapm/tlapm/bin/tlapm --solver z3 --cleanfp Liveness.tla > /work/full.txt 2>&1
  echo "exit=$?" >> /work/full.txt
  chmod -R 777 /work 2>/dev/null
'
echo "=== summary ==="
grep -aE "[0-9]+ obligation|All [0-9]+|exit=" /tmp/tla/full.txt | tail -3
echo "=== failing goals @ line ==="
grep -aA40 "Could not prove or check" /tmp/tla/full.txt | grep -aE "^ +PROVE|Liveness.tla.*line [0-9]+" | sed -E 's/^ +PROVE +/GOAL: /; s/.*line ([0-9]+),.*/   @L\1/' | paste - - | head -40
echo "DOCKER_TLAPM16_DONE"
