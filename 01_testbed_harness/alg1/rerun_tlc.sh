#!/usr/bin/env bash
set -e
TLA_DIR=$HOME/tla
JAVA=$HOME/jdk17/bin/java
cp "/mnt/d/프랑스 업데이트/TNSE 스페셜이슈 논문/IS-Raft-LAC/formal/tla/BORA.tla" $TLA_DIR/
cd $TLA_DIR
$JAVA -XX:+UseParallelGC -cp tla2tools.jar tlc2.TLC \
  -config BORA.cfg -workers 4 -deadlock BORA.tla 2>&1 | tee tlc_run2.log | tail -50
echo
echo "TLC_RERUN_DONE"
