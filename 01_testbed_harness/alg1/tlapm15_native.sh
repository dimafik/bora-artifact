#!/usr/bin/env bash
# Run the RELEASED tlapm 1.5.0 (~/tlaps, has Isabelle/Zenon/SMT, glibc-OK) natively.
SRC="/mnt/d/프랑스 업데이트/TNSE 스페셜이슈 논문/IS-Raft-LAC/formal/tla"
cd "$SRC" || exit 1
rm -rf .tlacache
echo "=== tlapm 1.5 version ==="
~/tlaps/bin/tlapm --version 2>&1 | head -1
echo "=== run Liveness.tla (native 1.5) ==="
timeout 2400 ~/tlaps/bin/tlapm --cleanfp Liveness.tla > /tmp/full15.txt 2>&1
echo "exit=$?"
grep -aE "[0-9]+ obligation|All [0-9]+ obl|proved" /tmp/full15.txt | tail -3
echo "=== failing goals ==="
grep -aA40 "Could not prove or check" /tmp/full15.txt | grep -aE "^ +PROVE|Liveness.tla.*line [0-9]+" | sed -E 's/^ +PROVE +/GOAL: /; s/.*line ([0-9]+),.*/   @L\1/' | paste - - | head -30
echo "NATIVE15_DONE"
