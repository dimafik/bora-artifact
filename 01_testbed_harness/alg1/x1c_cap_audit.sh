#!/usr/bin/env bash
# X1-c - does the predictor actually enforce |B_t| < f - r ?  (R2-3)
#
# WHY THIS IS SEPARATE.  x1_closedloop.sh forces elections with `docker pause`,
# which uses the cgroup freezer: the process stops but the kernel still completes
# TCP handshakes on its listening socket, so the RTT probe connects successfully
# and a paused orderer never registers as unresponsive.  Measured: zero RTT_FAIL
# sentinels and zero non-empty `unresponsive` sets across a whole pilot.  r is
# therefore pinned at 0 for the entire headline run and the cap rule is never
# exercised there.  `docker stop` closes the port for real, so r fires with no
# change to the probe -- which matters, because the RTT feed is the ML model's
# input and must not be altered to suit an audit.
#
# WHAT IT CHECKS.  Algorithm 1 substep (c) is  B_t <- top(p_t, H_t, f - r - 1).
# Degrade MORE nodes than the cap allows, then raise r one node at a time and
# check that the emitted blacklist shrinks in lockstep:
#
#     k (stopped)   r   cap = f-r-1   risky   expected |B_t|
#         0         0        4          4          4
#         1         1        3          4          3
#         2         2        2          4          2
#         3         3        1          4          1
#         4         4        0          4          0     <- stands down entirely
#
# The k=4 row is the N=5 degeneracy disclosed in §II-D, reproduced deliberately at
# N=11: once real failures exhaust the budget BORA yields to vanilla Raft.
#
# NO FORCED ELECTIONS.  The cap is a property of what the predictor emits, not of
# who wins an election, so this samples bt.json directly.  That keeps it to a few
# minutes and keeps it independent of election randomness.
#
# PRECONDITION: an N=11 cluster is already up (this does NOT rebuild it) and
# predictor_daemon_n.py is running on the host with N=11 f=5.
#
# Usage: x1c_cap_audit.sh [N] [delay_ms]
set -u

N="${1:-11}"; DLY="${2:-200}"
F=$(( (N - 1) / 2 ))
DEGRADED=(3 5 8 11)        # delayed by netem; more than any cap below allows
STOPPOOL=(2 4 6 7)         # healthy nodes stopped one at a time to raise r
SAMPLES=60                 # bt.json samples per level (~30 s at 0.5 s)

D=/mnt/d/fabric-d2
R=$D/results
BT=$R/bt.json
FEED=$R/rtt_feed.csv
export PATH=/tmp/bin:$D/fabric-samples/bin-linux/bin:/usr/local/bin:/usr/bin:/bin
export N_ORD="$N"

host(){ [ "$1" = 1 ] && echo orderer || echo "orderer$1"; }
cont(){ echo "$(host $1).example.com"; }

OUT="$R/x1c_N${N}_$(date +%Y%m%d-%H%M%S)"; mkdir -p "$OUT"
DCONT=(); for t in "${DEGRADED[@]}"; do DCONT+=("$(cont $t)"); done
DLIST=$(IFS=';'; echo "${DEGRADED[*]}")

{ echo "X1-c cap audit: N=$N f=$F degraded=[$DLIST] stop_pool=[$(IFS=';'; echo "${STOPPOOL[*]}")]"
  echo "expected cap by k: $(for k in 0 1 2 3 4; do printf '%d ' $(( F - k - 1 < 0 ? 0 : F - k - 1 )); done)"; } | tee "$OUT/timeline.txt"

# Liveness floor: quorum is floor(N/2)+1; never stop so many that we lose it.
QUORUM=$(( N / 2 + 1 ))
MAXSTOP=$(( N - QUORUM ))
[ "${#STOPPOOL[@]}" -le "$MAXSTOP" ] || { echo "stop pool ${#STOPPOOL[@]} would break quorum (max $MAXSTOP)"; exit 1; }

bl_of(){ printf '%s' "$1" | grep -oE '"blacklist" *: *\[[0-9, ]*\]' | grep -oE '\[[0-9, ]*\]' | tr -d '[] '; }
num_of(){ printf '%s' "$2" | grep -oE "\"$1\" *: *[0-9]+" | grep -oE '[0-9]+$'; }
bl_size(){ local b; b=$(bl_of "$1"); [ -z "$b" ] && { echo 0; return; }; printf '%s' "$b" | tr ',' '\n' | grep -c '[0-9]'; }
snap(){ [ -f "$BT" ] && tr -d '\n' < "$BT" || echo '{}'; }
leader_id(){ local id o all=""; for id in $(seq 1 "$N"); do o=$(cont $id)
    all+="$(docker logs --tail 200 "$o" 2>/dev/null | grep -aE 'Raft leader changed: [0-9]+ -> [0-9]+')"$'\n'; done
  printf '%s' "$all" | grep -aE 'Raft leader changed' | sort | tail -1 | grep -aoE '\-> [0-9]+' | grep -aoE '[0-9]+' | tail -1; }

cleanup(){
  echo "restoring stopped orderers..." | tee -a "$OUT/timeline.txt"
  for i in "${STOPPOOL[@]}"; do docker start "$(cont $i)" >/dev/null 2>&1 || true; done
  rm -f /tmp/push.on; [ -n "${PUSH_PID:-}" ] && kill "$PUSH_PID" 2>/dev/null
  docker rm -f pumba-x1c rtt-probe-x1c >/dev/null 2>&1
}
trap cleanup EXIT INT TERM

# ---------------------------------------------------------------- probe + attack
docker rm -f rtt-probe-x1c >/dev/null 2>&1; rm -f "$FEED"
docker run -d --name rtt-probe-x1c --network fabric_test -v /mnt/d/fabric-d2:/feed \
  -v "$D/alg1/rtt_probe_n.py:/rtt_probe.py" -e FEED=/feed/results/rtt_feed.csv -e N="$N" \
  python:3.11-slim python /rtt_probe.py >/dev/null 2>&1
docker rm -f pumba-x1c >/dev/null 2>&1
docker run -d --name pumba-x1c -v /var/run/docker.sock:/var/run/docker.sock gaiaadm/pumba:latest \
  --log-level warning netem --tc-image gaiadocker/iproute2 --duration 30m \
  delay --time "$DLY" "${DCONT[@]}" >/dev/null 2>&1

PUSH_PID=""
rm -f /tmp/push.on; N_ORD="$N" bash "$D/alg1/push_advice.sh" >"$OUT/pusher.log" 2>&1 & PUSH_PID=$!

echo "settling 40s so the detector sees the degraded set..." | tee -a "$OUT/timeline.txt"
sleep 40

echo "k,stopped,samples,r_mode,cap_mode,bt_size_mode,bt_mode,expected_cap,expected_size,cap_ok,size_ok,leader,advice_on_o1" > "$OUT/cap_audit.csv"
echo "k,sample_idx,r,cap,bt_size,bt" > "$OUT/samples.csv"

FAILED=0
for k in 0 1 2 3 4; do
  if [ "$k" -gt 0 ]; then
    victim=${STOPPOOL[$((k-1))]}
    echo "--- k=$k: stopping orderer$victim ---" | tee -a "$OUT/timeline.txt"
    docker stop "$(cont $victim)" >/dev/null 2>&1
    # UNRESP_W=6 samples at 0.3 s plus the model window; 20 s is ample.
    sleep 20
  else
    echo "--- k=0: no orderer stopped ---" | tee -a "$OUT/timeline.txt"
  fi

  declare -A RC=() CC=() SC=() BC=()
  for s in $(seq 1 "$SAMPLES"); do
    b=$(snap)
    r=$(num_of r "$b"); c=$(num_of cap "$b"); sz=$(bl_size "$b"); lst=$(bl_of "$b" | tr ',' ';')
    RC[${r:-NA}]=$(( ${RC[${r:-NA}]:-0} + 1 ))
    CC[${c:-NA}]=$(( ${CC[${c:-NA}]:-0} + 1 ))
    SC[$sz]=$(( ${SC[$sz]:-0} + 1 ))
    BC[${lst:-empty}]=$(( ${BC[${lst:-empty}]:-0} + 1 ))
    echo "$k,$s,${r:-NA},${c:-NA},$sz,${lst:-}" >> "$OUT/samples.csv"
    sleep 0.5
  done
  mode(){ local -n A=$1; local best="" bn=0 key; for key in "${!A[@]}"; do [ "${A[$key]}" -gt "$bn" ] && { bn=${A[$key]}; best=$key; }; done; echo "$best"; }
  RM=$(mode RC); CM=$(mode CC); SM=$(mode SC); BM=$(mode BC)

  EC=$(( F - k - 1 )); [ "$EC" -lt 0 ] && EC=0
  ES=$(( ${#DEGRADED[@]} < EC ? ${#DEGRADED[@]} : EC ))
  COK=$([ "$CM" = "$EC" ] && echo yes || echo NO)
  SOK=$([ "$SM" = "$ES" ] && echo yes || echo NO)
  [ "$COK" = NO ] && FAILED=$((FAILED+1))
  [ "$SOK" = NO ] && FAILED=$((FAILED+1))

  LD=$(leader_id); LD="${LD:-none}"
  ADV=$(docker exec "$(cont 1)" sh -c 'cat /tmp/bora-advice.json' 2>/dev/null | tr -d '\n' | tr ',' ';')

  echo "$k,${STOPPOOL[$((k>0?k-1:0))]},$SAMPLES,$RM,$CM,$SM,$BM,$EC,$ES,$COK,$SOK,$LD,\"$ADV\"" >> "$OUT/cap_audit.csv"
  printf "  k=%d  r=%-3s cap=%-3s |B_t|=%-3s B_t=[%s]   expect cap=%d size=%d   cap:%s size:%s   leader=%s\n" \
    "$k" "$RM" "$CM" "$SM" "$BM" "$EC" "$ES" "$COK" "$SOK" "$LD" | tee -a "$OUT/summary.txt"
done

echo | tee -a "$OUT/summary.txt"
if [ "$FAILED" -eq 0 ]; then
  echo "X1C_PASS: |B_t| tracked f-r-1 at every level, including stand-down at cap=0" | tee -a "$OUT/summary.txt"
else
  echo "X1C_FAIL: $FAILED mismatches - see cap_audit.csv" | tee -a "$OUT/summary.txt"
fi
echo "out=$OUT"
