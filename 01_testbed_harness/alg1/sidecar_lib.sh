# shared: process-based sidecar liveness (stale socket file is NOT enough)
#
# ALL_ORD is derived from N_ORD so the same library serves the X1 sweep
# (N = 7, 9, 11, 15, 21).  It was a fixed five-element list, which silently
# limited every consumer to the first five orderers; a pusher driving an N=21
# cluster would have left orderers 6..21 with stale advice and no error.
# The default of 5 reproduces the previous list exactly.
: "${N_ORD:=5}"
ALL_ORD=()
for _i in $(seq 1 "$N_ORD"); do
  if [ "$_i" = 1 ]; then ALL_ORD+=(orderer.example.com); else ALL_ORD+=("orderer${_i}.example.com"); fi
done
unset _i
sidecar_alive(){ # $1=container ; 0 if a bora-sidecar PROCESS is running
  docker exec "$1" sh -c 'cat /proc/[0-9]*/comm 2>/dev/null | grep -q "^bora-sidecar$"' 2>/dev/null
}
start_sidecar(){ # $1=container ; kill stale, remove stale socket, start, verify
  docker exec "$1" sh -c 'pkill -f bora-sidecar 2>/dev/null; sleep 0.2; rm -f /var/run/raft-advisor.sock' 2>/dev/null
  docker exec -d "$1" sh -c 'setsid /tmp/bora-sidecar >/tmp/bora-sidecar.log 2>&1 </dev/null' 2>/dev/null
  sleep 0.6
}
ensure_sidecar(){ sidecar_alive "$1" || start_sidecar "$1"; }
ensure_all_sidecars(){ local o; for o in "${ALL_ORD[@]}"; do ensure_sidecar "$o"; done; }
