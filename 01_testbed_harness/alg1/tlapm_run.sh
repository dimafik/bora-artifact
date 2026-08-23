#!/usr/bin/env bash
export PATH="$HOME/tlaps/bin:$PATH"
TLADIR="/mnt/d/프랑스 업데이트/TNSE 스페셜이슈 논문/IS-Raft-LAC/formal/tla"
cd "$TLADIR" || exit 1
echo "=== tlapm version ==="
tlapm --version 2>&1 | head -1
echo "=== tlapm proving BORA.tla (refinement + TypeOK) ==="
timeout 1200 tlapm --cleanfp BORA.tla 2>&1 | grep -avE "screen size is bogus" | tail -40
echo "=== TLAPM_DONE ==="
