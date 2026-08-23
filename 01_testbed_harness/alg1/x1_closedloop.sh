#!/usr/bin/env bash
# X1 - closed-loop predictor experiment (R2-1), multi-target sweep version.
#
# Derived from nsweep.sh.  nsweep.sh compares baseline [] against an
# OPERATOR-SUPPLIED [3]; that is exactly what Reviewer 2 objected to.  This
# script keeps the same forced-election harness and adds a third arm in which
# the blacklist is produced by the live predictor, so the learner - not the
# operator - drives the election outcome.
#
#   Arm A  vanilla     blacklist always []
#   Arm B  oracle      blacklist = the true target set   (old headline, now an ablation)
#   Arm C  predictor   blacklist from bt.json via pusher (the new headline)
#
# TARGET COUNT.  A single degraded node makes the baseline win-rate track the
# chance share 1/(N-1), which collapses from 16.7% at N=7 to 5% at N=21: the
# effect would look like it vanishes with scale.  Degrading cap = f-r-1 nodes
# instead inflates the baseline to 40% at N=21, which invites the opposite
# charge of making the large-N case artificially easy.  So the target count is
# pinned to the chance share, not to the cap:
#
#     m = round((N-1)/6),  clamped to 1 <= m <= cap
#
#     N     f   cap   m   chance share m/(N-1)
#     7     3    1    1        16.7%
#     9     4    2    1        12.5%
#    11     5    3    2        20.0%
#    15     7    5    2        14.3%
#    21    10    8    3        15.0%
#
# The chance share stays flat and N=21 sits BELOW N=7, so scale cannot be
# accused of inflating the baseline.  N=7 and N=9 keep m=1, which reproduces the
# already-published single-target configuration exactly.  Whether the cap itself
# is enforced is a separate mechanism check (X1-c), deliberately not folded into
# this headline experiment.
#
# Usage: x1_closedloop.sh <N> [seeds] [elections] [delay_ms]
#        x1_closedloop.sh 11 4 10 200
#
# Prerequisites (see X1_폐루프실험_설계):
#   - predictor_daemon_n.py running on the host:  python predictor_daemon_n.py 0.65 <N> <f>
#   - orderer-bora-v4.bin and bora-sidecar-v3.bin present in results/
set -u

N="${1:?need N}"; SEEDS="${2:-10}"; NE="${3:-12}"; DLY="${4:-200}"
F=$(( (N - 1) / 2 ))

# r = 1: the harness forces each election by pausing the current leader, so one
# orderer is Raft-observed unhealthy for the whole election window.
R_EXPECT=1
CAP=$(( F - R_EXPECT - 1 ))
M=$(( (N - 1 + 3) / 6 ))                     # round((N-1)/6)
[ "$M" -lt 1 ] && M=1
[ "$M" -gt "$CAP" ] && M="$CAP"
[ "$M" -lt 1 ] && { echo "N=$N degenerate: cap=$CAP leaves no advisory budget"; exit 1; }

# Targets spread evenly around the ring, anchored at orderer3 so that m=1 gives
# exactly the published single-target configuration.
TARGETS=()
for k in $(seq 0 $((M - 1))); do
  TARGETS+=( $(( ( 2 + (k * N + M / 2) / M ) % N + 1 )) )
done
# Two renderings on purpose.  TLIST_JSON goes into the advice file, which must be
# valid JSON.  TLIST_CSV goes into the result CSV, where an embedded comma would
# shift every downstream column; the pilot lost its cap audit to exactly that.
TLIST_JSON=$(IFS=,; echo "${TARGETS[*]}")
TLIST_CSV=$(IFS=';'; echo "${TARGETS[*]}")
[ "$(printf '%s\n' "${TARGETS[@]}" | sort -u | wc -l)" -eq "$M" ] || { echo "target set not unique: $TLIST_JSON"; exit 1; }

D=/mnt/d/fabric-d2
R=$D/results
BIN=$R/orderer-bora-v4.bin
SIDE=$R/bora-sidecar-v3.bin
BT=$R/bt.json
FEED=$R/rtt_feed.csv
export PATH=/tmp/bin:$D/fabric-samples/bin-linux/bin:/usr/local/bin:/usr/bin:/bin
export N_ORD="$N"                            # push_advice.sh / sidecar_lib.sh fan-out

host(){ [ "$1" = 1 ] && echo orderer || echo "orderer$1"; }
cont(){ echo "$(host $1).example.com"; }

OUT="$R/x1_N${N}_$(date +%Y%m%d-%H%M%S)"; mkdir -p "$OUT"
ORD=(); for i in $(seq 1 "$N"); do ORD+=("$(cont $i)"); done
TCONT=(); for t in "${TARGETS[@]}"; do TCONT+=("$(cont $t)"); done

CHANCE=$(awk -v m="$M" -v n="$N" 'BEGIN{printf "%.1f", 100*m/(n-1)}')
{ echo "X1 closed loop: N=$N f=$F cap=$CAP m=$M targets=[$TLIST_JSON] chance=${CHANCE}%"
  echo "seeds=$SEEDS elec=$NE delay=${DLY}ms"; } | tee "$OUT/timeline.txt"

# The attack must outlive the whole run.  A fixed --duration with --interval
# cycles the netem off for the gap between cycles, which would silently label a
# fraction of elections as attacked when they were not.
PER=$(( 13 + (8 * N) / 10 ))                 # seconds per election, incl. log scraping
ATT_MIN=$(( (SEEDS * NE * 3 * PER * 16 / 10) / 60 + 5 ))
echo "budget: ~${PER}s/election, attack window ${ATT_MIN}m" | tee -a "$OUT/timeline.txt"

# ---------------------------------------------------------------- daemon gate
# Checked HERE, before the twelve-minute bring-up, and independently of whatever
# the daemon launcher reported.
#
# The N=9 run produced a whole invalid arm because the predictor had never
# started: bt.json stayed frozen at the previous N's output, the pusher replayed
# it for an hour, and Arm C was a second oracle arm wearing the predictor's name.
# The launcher had printed success. Nothing downstream noticed. Two independent
# properties are therefore verified against the file the pusher actually reads:
#   (a) it is being rewritten right now  -> a daemon is alive and publishing
#   (b) its cap matches THIS N's f       -> that daemon is running THIS N
# Either one alone would have missed the N=9 failure: the file existed and its
# contents were well-formed; they were simply someone else's and forty minutes old.
gate_daemon(){
  local age b r c want
  [ -f "$BT" ] || { echo "GATE FAIL: $BT missing - is predictor_daemon_n.py running?"; exit 1; }
  age=$(( $(date +%s) - $(stat -c %Y "$BT") ))
  if [ "$age" -gt 15 ]; then
    echo "GATE FAIL: $BT is ${age}s stale - the daemon is not publishing."
    echo "  (it also goes stale when rtt_feed.csv is absent, since the daemon"
    echo "   needs >=10 rows before it writes; check both)"
    exit 1
  fi
  b=$(tr -d '\n' < "$BT")
  r=$(printf '%s' "$b" | grep -oE '"r" *: *[0-9]+' | grep -oE '[0-9]+$')
  c=$(printf '%s' "$b" | grep -oE '"cap" *: *[0-9]+' | grep -oE '[0-9]+$')
  [ -n "$r" ] && [ -n "$c" ] || { echo "GATE FAIL: bt.json carries no r/cap - stale daemon build"; exit 1; }
  want=$(( F - r - 1 )); [ "$want" -lt 0 ] && want=0
  if [ "$c" != "$want" ]; then
    echo "GATE FAIL: bt.json says cap=$c, but N=$N f=$F with r=$r implies cap=$want."
    echo "  The running daemon belongs to a different N. Restart it:"
    echo "  powershell -File alg1/restart_daemon.ps1 $N $F"
    exit 1
  fi
  echo "  daemon gate OK: bt.json ${age}s old, r=$r cap=$c consistent with f=$F" | tee -a "$OUT/timeline.txt"
}
gate_daemon

# ---------------------------------------------------------------- cluster bring-up
# Remove orderers left over from a LARGER previous cluster.  The bring-up helper
# runs `docker compose -f ${N}node-raft.yaml down`, and that compose file only
# knows orderer1..N, so stepping DOWN in N (11 -> 9) strands orderer10 and
# orderer11.  Measured on this host: two such orphans kept retrying TLS
# handshakes against the live cluster at roughly 12 log lines per second.  They
# are not consenters and cannot affect safety, but they are an uncontrolled
# variable across an N-sweep, so they are cleared before every run.
docker ps -a --format '{{.Names}}' 2>/dev/null | grep -E '^orderer[0-9]*\.example\.com$' | while read -r o; do
  idx=$(printf '%s' "$o" | grep -oE '^orderer[0-9]+' | grep -oE '[0-9]+')
  idx=${idx:-1}                       # bare "orderer.example.com" is node 1
  if [ "$idx" -gt "$N" ]; then
    echo "  removing orphan $o (from a previous N>$N run)" | tee -a "$OUT/timeline.txt"
    docker rm -f "$o" >/dev/null 2>&1
  fi
done

bash "$D/alg1/nsweep_bringup.sh" "$N" 2>&1 | tee -a "$OUT/timeline.txt" || {
  echo "bring-up helper failed; run nsweep.sh $N once, then re-run" | tee -a "$OUT/timeline.txt"; exit 1; }

# ---------------------------------------------------------------- advice paths
# Arm A/B: operator writes the advice file directly (nsweep.sh semantics).
set_all(){ for o in "${ORD[@]}"; do
  docker exec "$o" sh -c "printf '%s' '{\"blacklist\":$1,\"seq\":1,\"fail_open\":false}' > /tmp/bora-advice.json" 2>/dev/null
done; }

# Arm C: the pusher mirrors the predictor's bt.json onto every orderer.
PUSH_PID=""
start_pusher(){ rm -f /tmp/push.on; N_ORD="$N" bash "$D/alg1/push_advice.sh" >"$OUT/pusher.log" 2>&1 & PUSH_PID=$!; }
stop_pusher(){ rm -f /tmp/push.on; [ -n "$PUSH_PID" ] && kill "$PUSH_PID" 2>/dev/null; PUSH_PID=""; }

# ---------------------------------------------------------------- probe + attack
start_probe(){
  docker rm -f rtt-probe >/dev/null 2>&1
  rm -f "$FEED"
  docker run -d --name rtt-probe --network fabric_test -v /mnt/d/fabric-d2:/feed \
    -v "$D/alg1/rtt_probe_n.py:/rtt_probe.py" -e FEED=/feed/results/rtt_feed.csv -e N="$N" \
    python:3.11-slim python /rtt_probe.py >/dev/null 2>&1
}
start_attack(){
  docker rm -f pumba-x1 >/dev/null 2>&1
  docker run -d --name pumba-x1 -v /var/run/docker.sock:/var/run/docker.sock gaiaadm/pumba:latest \
    --log-level warning netem --tc-image gaiadocker/iproute2 --duration "${ATT_MIN}m" \
    delay --time "$DLY" "${TCONT[@]}" >/dev/null 2>&1
}
stop_attack(){ docker stop pumba-x1 >/dev/null 2>&1; docker rm -f pumba-x1 >/dev/null 2>&1; }
# If pumba dies the run silently becomes a no-attack run, so check at every arm.
check_attack(){
  if [ -z "$(docker ps -q -f name=pumba-x1 2>/dev/null)" ]; then
    echo "WARN $(date +%s) pumba-x1 not running at $1 - restarting" | tee -a "$OUT/timeline.txt"
    start_attack; sleep 3
  fi
}

# ---------------------------------------------------------------- bt.json parsing
# Membership by explicit list compare, never by regex word boundary: searching
# for "1" inside "[10, 17]" is exactly the kind of match that silently corrupts
# a whole campaign.
snap_bt(){ [ -f "$BT" ] && tr -d '\n' < "$BT" || echo '{}'; }
bl_of(){ printf '%s' "$1" | grep -oE '"blacklist" *: *\[[0-9, ]*\]' | grep -oE '\[[0-9, ]*\]' | tr -d '[] '; }
in_list(){ case ",$2," in *",$1,"*) return 0;; esac; return 1; }
count_hits(){ local bl n=0 t; bl=$(bl_of "$1"); for t in "${TARGETS[@]}"; do in_list "$t" "$bl" && n=$((n+1)); done; echo "$n"; }
bl_size(){ local bl; bl=$(bl_of "$1"); [ -z "$bl" ] && { echo 0; return; }; printf '%s' "$bl" | tr ',' '\n' | grep -c '[0-9]'; }
num_of(){ printf '%s' "$2" | grep -oE "\"$1\" *: *[0-9]+" | grep -oE '[0-9]+$'; }

# One snapshot -> the five fields the audit needs, as comma-free CSV cells.
# Emits: hits,size,list,r,cap
snap_fields(){
  local b="$1" h s l r c
  h=$(count_hits "$b"); s=$(bl_size "$b"); l=$(bl_of "$b" | tr ',' ';')
  r=$(num_of r "$b"); c=$(num_of cap "$b")
  echo "$h,$s,${l:-},${r:-NA},${c:-NA}"
}

# Preserve the raft logs per arm.  Campaign suppression is the primary metric now
# and it is reconstructed from these logs; if the run dies and the cluster is torn
# down, unsaved logs are unrecoverable evidence.
dump_logs(){
  local tag="$1" i o; mkdir -p "$OUT/logs"
  for i in $(seq 1 "$N"); do o=$(cont $i)
    docker logs "$o" >"$OUT/logs/${tag}_orderer${i}.log" 2>&1 || true
  done
}

# T_det: first wall-clock time at which every target is held by the predictor.
T_DET=""; DET_PID=""
watch_det(){ ( while :; do
    [ "$(count_hits "$(snap_bt)")" = "$M" ] && { date +%s.%N > "$OUT/t_det.txt"; break; }
    sleep 0.1; done ) & DET_PID=$!; }

heal(){ for o in "${ORD[@]}"; do docker exec -d "$o" sh -c 'cat /proc/[0-9]*/comm 2>/dev/null | grep -q "^bora-sidecar$" || { rm -f /var/run/raft-advisor.sock; setsid /tmp/bora-sidecar >/tmp/bs.log 2>&1 </dev/null; }' 2>/dev/null || true; done; }
leader_id(){ local id o all=""; for id in $(seq 1 "$N"); do o=$(cont $id); all+="$(docker logs --tail 400 "$o" 2>&1 | grep -aE 'Raft leader changed: [0-9]+ -> [0-9]+')"$'\n'; done; local y; y=$(printf '%s' "$all" | grep -aE 'Raft leader changed' | sort | tail -1 | grep -aoE '\-> [0-9]+' | grep -aoE '[0-9]+'); echo "${y:-0}"; }

RUN=/tmp/x1_heal; touch $RUN; ( while [ -f $RUN ]; do heal; sleep 3; done ) & HP=$!

# Two B_t snapshots per election.  The "pre" one is taken before the leader is
# paused, so it always shows r=0; the cap the paper claims to enforce during an
# election is f-r-1 with r=1, which only exists while the leader is frozen.  The
# pilot recorded only the pre snapshot and therefore never audited the rule at the
# moment it matters.  The "mid" one is taken 5s into the 9s pause.
echo "arm,N,f,m,targets,seed,elec_idx,t_start,t_end,window,hits,size,list,r,cap,hits_mid,size_mid,list_mid,r_mid,cap_mid,leader_before,lb_was_target,leader_after,target_won,live" > "$OUT/elections.csv"
echo "arm,N,m,chance_pct,seed,target_wins,elec,live,w0,wp,w1,w1_wins" > "$OUT/results.csv"

# ---------------------------------------------------------------- election phase
# One forced election: pause the current leader past the election timeout, read
# the new leader while the old one is still frozen, unpause.  Identical timing to
# nsweep.sh so Arm A/B stay comparable with the published numbers.
phase(){
  local arm="$1" seed="$2"
  WINS=0; LIVE=0; W0=0; W1=0; WP=0; W1W=0
  local k L LC NL TS TE WIN PRE MID HITS LBT
  for k in $(seq 1 "$NE"); do
    TS=$(date +%s.%N)
    PRE=$(snap_fields "$(snap_bt)")
    HITS=${PRE%%,*}
    if [ "$HITS" = "$M" ]; then WIN=W1; elif [ "$HITS" = 0 ]; then WIN=W0; else WIN=Wp; fi

    L=$(leader_id); [ "$L" = 0 ] && L=2; LC=$(cont $L)
    # The paused leader may itself be a target; that election cannot be won by it,
    # so record the fact rather than letting it quietly bias the baseline.
    LBT=0; in_list "$L" "$TLIST_JSON" && LBT=1

    # Pause budget stays 9s in total so Arm A/B remain comparable with the
    # published cadence; the mid-pause read just splits the existing wait.
    docker pause "$LC" >/dev/null 2>&1
    sleep 5
    MID=$(snap_fields "$(snap_bt)")
    sleep 4
    NL=$(leader_id)
    docker unpause "$LC" >/dev/null 2>&1; sleep 4
    TE=$(date +%s.%N)

    local won=0 live=0
    in_list "$NL" "$TLIST_JSON" && { won=1; WINS=$((WINS+1)); }
    [ "$NL" != 0 ] && [ "$NL" != "$L" ] && { live=1; LIVE=$((LIVE+1)); }
    case "$WIN" in
      W1) W1=$((W1+1)); [ "$won" = 1 ] && W1W=$((W1W+1));;
      Wp) WP=$((WP+1));;
      *)  W0=$((W0+1));;
    esac

    echo "$arm,$N,$F,$M,$TLIST_CSV,$seed,$k,$TS,$TE,$WIN,$PRE,$MID,$L,$LBT,$NL,$won,$live" >> "$OUT/elections.csv"
    echo "[$arm s$seed] e$k ($WIN hits=$HITS/$M): $L->$NL won=$won pre=[$PRE] mid=[$MID]" >> "$OUT/elections.log"
  done
}

record(){ echo "$1,$N,$M,$CHANCE,$2,$WINS,$NE,$LIVE,$W0,$WP,$W1,$W1W" >> "$OUT/results.csv"
  echo "  $1 s$2: target $WINS/$NE  live $LIVE/$NE  (W0=$W0 Wp=$WP W1=$W1 W1wins=$W1W)" | tee -a "$OUT/summary.txt"; }

# ---------------------------------------------------------------- main
start_probe; sleep 3
start_attack
echo "ATTACK_ONSET=$(date +%s.%N) targets=[$TLIST_JSON]" | tee -a "$OUT/timeline.txt"
watch_det

for s in $(seq 1 "$SEEDS"); do
  check_attack "s$s/A"; stop_pusher; set_all "[]";             sleep 2; phase "A_vanilla"   "$s"; record "A_vanilla"   "$s"; dump_logs "s${s}_A"
  check_attack "s$s/B"; stop_pusher; set_all "[$TLIST_JSON]";  sleep 2; phase "B_oracle"    "$s"; record "B_oracle"    "$s"; dump_logs "s${s}_B"
  check_attack "s$s/C"; start_pusher;                          sleep 2; phase "C_predictor" "$s"; record "C_predictor" "$s"; dump_logs "s${s}_C"
done

stop_pusher; stop_attack; set_all "[]"
[ -n "$DET_PID" ] && kill "$DET_PID" 2>/dev/null
rm -f $RUN; kill $HP 2>/dev/null || true
docker rm -f rtt-probe >/dev/null 2>&1

echo "T_det=$(cat "$OUT/t_det.txt" 2>/dev/null || echo NA)" | tee -a "$OUT/timeline.txt"
echo "X1_N${N}_DONE  m=$M targets=[$TLIST_JSON] chance=${CHANCE}%"; cat "$OUT/results.csv"
