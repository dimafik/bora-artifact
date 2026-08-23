#!/usr/bin/env bash
# Quick de-risk on the LIVE N=7 cluster: confirm (1) sidecars survive pause/unpause,
# (2) BORA [3] suppresses orderer3 to 0 wins while baseline [] lets it win sometimes.
set -u
N=7
export PATH=/tmp/bin:/mnt/d/fabric-d2/fabric-samples/bin-linux/bin:/usr/local/bin:/usr/bin:/bin
cont(){ if [ "$1" = 1 ]; then echo orderer.example.com; else echo "orderer$1.example.com"; fi; }
ORD=(); for i in $(seq 1 "$N"); do ORD+=("$(cont $i)"); done
leader_id(){ local id o all=""; for id in $(seq 1 "$N"); do o=$(cont $id); all+="$(docker logs --tail 400 "$o" 2>&1 | grep -aE 'Raft leader changed: [0-9]+ -> [0-9]+')"$'\n'; done; local y; y=$(printf '%s' "$all" | grep -aE 'Raft leader changed' | sort | tail -1 | grep -aoE '\-> [0-9]+' | grep -aoE '[0-9]+'); echo "${y:-0}"; }
sidecars_up(){ local n=0 o; for o in "${ORD[@]}"; do docker exec "$o" sh -c 'cat /proc/[0-9]*/comm 2>/dev/null | grep -q "^bora-sidecar$"' 2>/dev/null && n=$((n+1)); done; echo $n; }
set_all(){ for o in "${ORD[@]}"; do docker exec "$o" sh -c "printf '%s' '{\"blacklist\":$1,\"seq\":1,\"fail_open\":false}' > /tmp/bora-advice.json" 2>/dev/null; done; }
heal_once(){ for o in "${ORD[@]}"; do docker exec -d "$o" sh -c 'cat /proc/[0-9]*/comm 2>/dev/null | grep -q "^bora-sidecar$" || { rm -f /var/run/raft-advisor.sock; setsid /tmp/bora-sidecar >/tmp/bs.log 2>&1 </dev/null; }' 2>/dev/null || true; done; }

echo "=== (re)start sidecars ==="
heal_once; sleep 3; echo "sidecars up: $(sidecars_up)/$N"

run3(){ local lbl=$1 w=0 k L LC NL; for k in 1 2 3; do
  L=$(leader_id); [ "$L" = 0 ]&&L=2; LC=$(cont $L)
  docker pause "$LC" >/dev/null 2>&1; sleep 9
  NL=$(leader_id)
  docker unpause "$LC" >/dev/null 2>&1; sleep 4
  [ "$NL" = 3 ]&&w=$((w+1))
  echo "  [$lbl] e$k: $L->$NL (sidecars $(sidecars_up)/$N)"
done; echo "  [$lbl] o3_wins=$w/3"; }

echo "=== baseline [] ==="; set_all "[]"; sleep 2; run3 base
echo "=== BORA [3] ==="; set_all "[3]"; sleep 2; run3 bora
echo "VALIDATE_DONE"
