#!/usr/bin/env bash
docker run --rm -v /tmp:/host ubuntu:24.04 rm -rf /host/tla2
mkdir -p /tmp/tla2
cp /mnt/d/fabric-d2/alg1/MiniEnabled.tla /tmp/tla2/
docker run --rm -v /tmp/tlapm16:/tlapm -v /tmp/tla2:/work ubuntu:24.04 bash -c '
  apt-get update -qq >/dev/null 2>&1
  DEBIAN_FRONTEND=noninteractive apt-get install -y -qq z3 >/dev/null 2>&1
  cd /work; rm -rf .tlacache
  echo "=== default (zenon) ==="
  /tlapm/tlapm/bin/tlapm --cleanfp MiniEnabled.tla 2>&1 | grep -aiE "obligation|Could not|proved|error" | tail -6
  echo "=== z3 ==="
  /tlapm/tlapm/bin/tlapm --method z3 --cleanfp MiniEnabled.tla 2>&1 | grep -aiE "obligation|Could not|proved|error" | tail -6
'
echo MINI_DONE
