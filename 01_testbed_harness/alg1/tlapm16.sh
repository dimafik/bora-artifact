#!/usr/bin/env bash
TB=/tmp/tlapm16/tlapm/bin/tlapm
export PATH="/tmp/tlapm16/tlapm/bin:$PATH"
echo "=== tlapm 1.6 version ==="
"$TB" --version 2>&1 | head -3
echo "=== help: ExpandENABLED / solvers ==="
"$TB" --help 2>&1 | grep -iE "version|solver|method" | head -5
TLADIR="/mnt/d/프랑스 업데이트/TNSE 스페셜이슈 논문/IS-Raft-LAC/formal/tla"
cd "$TLADIR" || exit 1
echo "=== run on current Liveness.tla (OMITTED enabledness) to confirm tlapm 1.6 works ==="
timeout 1200 "$TB" --cleanfp Liveness.tla 2>&1 | grep -aiE "[0-9]+ obligation|Could not|Error|abnormally|omitted|All [0-9]|version" | grep -avE "screen size" | tail -12
echo "TLAPM16_DONE"
