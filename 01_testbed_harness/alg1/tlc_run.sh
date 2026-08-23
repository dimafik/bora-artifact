#!/usr/bin/env bash
JB=/tmp/jre/bin/java
JAR="/mnt/d/프랑스 업데이트/python/raft_for_EC2/tla2tools.jar"
TLADIR="/mnt/d/프랑스 업데이트/TNSE 스페셜이슈 논문/IS-Raft-LAC/formal/tla"
echo "=== java version ==="
"$JB" -version 2>&1 | head -1
echo "=== copying tla2tools into tla dir ==="
cp "$JAR" "$TLADIR/tla2tools.jar"
cd "$TLADIR" || exit 1
echo "=== running TLC on BORA.tla with LeaderAppendOnly property ==="
"$JB" -XX:+UseParallelGC -cp tla2tools.jar tlc2.TLC -config BORA_MC.cfg BORA.tla 2>&1 | tail -45
echo "=== TLC_DONE ==="
