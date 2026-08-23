#!/usr/bin/env bash
JB=/tmp/jre/bin/java
TLADIR="/mnt/d/프랑스 업데이트/TNSE 스페셜이슈 논문/IS-Raft-LAC/formal/tla"
cd "$TLADIR" || exit 1
echo "=== TLC cross-module refinement check (Spec => Van!Spec) ==="
"$JB" -XX:+UseParallelGC -cp tla2tools.jar tlc2.TLC -config BORA_REF.cfg BORA.tla 2>&1 | tail -25
echo "=== TLC_REF_DONE ==="
