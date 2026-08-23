#!/usr/bin/env bash
# Refresh alg1/model/ from the authoritative model tree.
#
# The daemon needs predictor/model.py and model_small/best.pt resolved relative
# to its working directory. The authoritative copy lives under a Korean path,
# which Windows PowerShell 5.1 mangles when a .ps1 without a UTF-8 BOM is run via
# `powershell -File` (this silently broke the N=9 run). alg1/model/ is an
# ASCII-only mirror; run this whenever the model or the daemon changes.
set -eu

SRC="/mnt/d/프랑스 업데이트/TNSE 스페셜이슈 논문/IS-Raft-LAC/submission/pivot_v26"
DST=/mnt/d/fabric-d2/alg1/model

[ -d "$SRC" ] || { echo "source tree not found: $SRC"; exit 1; }
mkdir -p "$DST"
rm -rf "$DST/predictor" "$DST/model_small"
cp -r "$SRC/predictor" "$DST/"
cp -r "$SRC/model_small" "$DST/"
cp /mnt/d/fabric-d2/alg1/predictor_daemon_n.py "$DST/predictor_daemon_n.py"

echo "refreshed $DST"
ls -1 "$DST"
cmp -s /mnt/d/fabric-d2/alg1/predictor_daemon_n.py "$DST/predictor_daemon_n.py" \
  && echo "daemon copy matches alg1/predictor_daemon_n.py" \
  || { echo "daemon copy DIFFERS"; exit 1; }
