#!/usr/bin/env bash
# Install portable Java (no sudo) + tla2tools.jar; run TLC.
set -e
JAVA_DIR=$HOME/jdk17
TLA_DIR=$HOME/tla
mkdir -p $JAVA_DIR $TLA_DIR

echo "[1/3] Install portable OpenJDK 17 (Adoptium Temurin)..."
if [ ! -f "$JAVA_DIR/bin/java" ]; then
  cd /tmp
  if [ ! -f openjdk17.tar.gz ]; then
    wget -q --show-progress -O openjdk17.tar.gz \
      'https://github.com/adoptium/temurin17-binaries/releases/download/jdk-17.0.10%2B7/OpenJDK17U-jre_x64_linux_hotspot_17.0.10_7.tar.gz'
  fi
  tar -xzf openjdk17.tar.gz -C $HOME
  EXTRACTED=$(ls -dt $HOME/jdk-17* | head -1)
  rm -rf $JAVA_DIR
  mv "$EXTRACTED" $JAVA_DIR
fi
$JAVA_DIR/bin/java -version 2>&1 | head -1

echo "[2/3] tla2tools.jar ..."
cd $TLA_DIR
if [ ! -f tla2tools.jar ]; then
  wget -q https://github.com/tlaplus/tlaplus/releases/download/v1.8.0/tla2tools.jar
fi
ls -lh tla2tools.jar

echo "[3/3] Run TLC on BORA.tla..."
cp "/mnt/d/프랑스 업데이트/TNSE 스페셜이슈 논문/IS-Raft-LAC/formal/tla/BORA.tla" \
   "/mnt/d/프랑스 업데이트/TNSE 스페셜이슈 논문/IS-Raft-LAC/formal/tla/BORA.cfg" \
   $TLA_DIR/
cd $TLA_DIR
$JAVA_DIR/bin/java -XX:+UseParallelGC -cp tla2tools.jar tlc2.TLC \
  -config BORA.cfg -workers 4 -deadlock BORA.tla 2>&1 | tee tlc_run.log | tail -60
echo
echo "TLC_RUN_DONE"
