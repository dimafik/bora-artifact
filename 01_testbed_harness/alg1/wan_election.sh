#!/usr/bin/env bash
# A-experiment: does the leadership EXCLUSION survive WAN-scale inter-orderer latency?
# Applies tc netem (40ms +- 10ms) to the Fabric docker bridge so every inter-orderer
# Raft packet pays a cross-region RTT, then re-runs the forced-election (pause/unpause)
# baseline [] vs BORA [3] on the LIVE cluster. The advisor dial is a unix socket and is
# NOT delayed, so this isolates "exclusion under WAN" from detection. Removes netem after.
set -u
export PATH=/tmp/bin:/mnt/d/fabric-d2/fabric-samples/bin-linux/bin:/usr/local/bin:/usr/bin:/bin
N=$(docker ps --filter name=orderer --format '{{.Names}}' | grep -c '^orderer')
echo "live orderers: $N"
cont(){ if [ "$1" = 1 ]; then echo orderer.example.com; else echo "orderer$1.example.com"; fi; }
ORD=(); for i in $(seq 1 "$N"); do ORD+=("$(cont $i)"); done
leader_id(){ local id o all=""; for id in $(seq 1 "$N"); do o=$(cont $id); all+="$(docker logs --tail 400 "$o" 2>&1 | grep -aE 'Raft leader changed: [0-9]+ -> [0-9]+')"$'\n'; done; local y; y=$(printf '%s' "$all" | grep -aE 'Raft leader changed' | sort | tail -1 | grep -aoE '\-> [0-9]+' | grep -aoE '[0-9]+'); echo "${y:-0}"; }
sidecars_up(){ local n=0 o; for o in "${ORD[@]}"; do docker exec "$o" sh -c 'cat /proc/[0-9]*/comm 2>/dev/null | grep -q "^bora-sidecar$"' 2>/dev/null && n=$((n+1)); done; echo $n; }
set_all(){ for o in "${ORD[@]}"; do docker exec "$o" sh -c "printf '%s' '{\"blacklist\":$1,\"seq\":1,\"fail_open\":false}' > /tmp/bora-advice.json" 2>/dev/null; done; }
heal(){ for o in "${ORD[@]}"; do docker exec -d "$o" sh -c 'cat /proc/[0-9]*/comm 2>/dev/null | grep -q "^bora-sidecar$" || { rm -f /var/run/raft-advisor.sock; setsid /tmp/bora-sidecar >/tmp/bs.log 2>&1 </dev/null; }' 2>/dev/null || true; done; }

# Inter-orderer WAN latency is injected per-orderer via a throwaway iproute2 container
# sharing each orderer's network namespace (Docker Desktop puts the bridge in the DD VM,
# unreachable from WSL, and the WSL distro has no tc -- so we cannot netem the host bridge).
# Applying netem to each orderer's eth0 delays its Raft links; the advisor UDS is unaffected.
OUT=/mnt/d/fabric-d2/results/wan_election_$(date +%H%M%S); mkdir -p "$OUT"
echo "label,N,seed,o3_wins,elec,live,wan_ms" > "$OUT/results.csv"

apply_wan(){ local o n=0; for o in "${ORD[@]}"; do docker run --rm --net "container:$o" --cap-add NET_ADMIN --entrypoint sh gaiadocker/iproute2 -c "tc qdisc replace dev eth0 root netem delay 40ms 10ms distribution normal" >/dev/null 2>&1 && n=$((n+1)); done; echo "$n"; }
verify_wan(){ docker run --rm --net "container:${ORD[0]}" --cap-add NET_ADMIN --entrypoint sh gaiadocker/iproute2 -c "tc qdisc show dev eth0" 2>/dev/null | grep -o "netem.*" | head -1; }
clear_wan(){ local o; for o in "${ORD[@]}"; do docker run --rm --net "container:$o" --cap-add NET_ADMIN --entrypoint sh gaiadocker/iproute2 -c "tc qdisc del dev eth0 root" >/dev/null 2>&1 || true; done; }

RUN=/tmp/wan_heal; touch $RUN; ( while [ -f $RUN ]; do heal; sleep 3; done ) & HP=$!
heal; sleep 4; echo "sidecars before WAN: $(sidecars_up)/$N"
echo "=== applying WAN netem 40ms+-10ms to each orderer eth0 ==="
echo "  applied to $(apply_wan)/$N orderers; qdisc=$(verify_wan)"
sleep 6; echo "sidecars after WAN: $(sidecars_up)/$N (unix socket unaffected)"

phase(){ WINS=0; LIVE=0; local k L LC NL; for k in $(seq 1 "$2"); do
    L=$(leader_id); [ "$L" = 0 ]&&L=2; LC=$(cont $L)
    docker pause "$LC" >/dev/null 2>&1; sleep 11
    NL=$(leader_id)
    docker unpause "$LC" >/dev/null 2>&1; sleep 5
    [ "$NL" = 3 ]&&WINS=$((WINS+1)); [ "$NL" != 0 ]&&[ "$NL" != "$L" ]&&LIVE=$((LIVE+1))
    echo "[$1] e$k: $L->$NL" >> "$OUT/elections.log"; done; }

NE=10
for s in 1 2; do
  set_all "[]"; sleep 2; phase "wan_base_s$s" $NE
  echo "  WAN N=$N base s$s: o3 $WINS/$NE live $LIVE/$NE" | tee -a "$OUT/summary.txt"
  echo "base,$N,$s,$WINS,$NE,$LIVE,40" >> "$OUT/results.csv"
  set_all "[3]"; sleep 2; phase "wan_bora_s$s" $NE
  echo "  WAN N=$N BORA s$s: o3 $WINS/$NE live $LIVE/$NE" | tee -a "$OUT/summary.txt"
  echo "bora,$N,$s,$WINS,$NE,$LIVE,40" >> "$OUT/results.csv"
done
set_all "[]"; rm -f $RUN; kill $HP 2>/dev/null || true
echo "=== clearing WAN netem ==="; clear_wan
echo "WAN_ELECTION_DONE"; cat "$OUT/results.csv"
