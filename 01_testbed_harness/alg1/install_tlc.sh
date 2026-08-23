#!/usr/bin/env bash
set -e
echo "[1/3] Install Java (OpenJDK 17)..."
if ! java -version 2>&1 | grep -q 'version'; then
  sudo apt-get update -qq
  sudo apt-get install -y openjdk-17-jre-headless
fi
java -version 2>&1 | head -1

echo "[2/3] Download tla2tools.jar..."
TLA=$HOME/tla
mkdir -p $TLA
cd $TLA
if [ ! -f tla2tools.jar ]; then
  wget -q https://github.com/tlaplus/tlaplus/releases/download/v1.8.0/tla2tools.jar
fi
ls -la $TLA/tla2tools.jar

echo "[3/3] Run TLC on BORA.tla..."
TLA_DIR=/mnt/d/프랑스\ 업데이트/TNSE\ 스페셜이슈\ 논문/IS-Raft-LAC/formal/tla
cp "$TLA_DIR/BORA.tla" "$TLA_DIR/BORA.cfg" $TLA/
cd $TLA
java -XX:+UseParallelGC -cp tla2tools.jar tlc2.TLC \
  -config BORA.cfg -workers 4 -deadlock BORA.tla 2>&1 | tee tlc_run.log | tail -40
echo
echo "TLC_RUN_OK"
