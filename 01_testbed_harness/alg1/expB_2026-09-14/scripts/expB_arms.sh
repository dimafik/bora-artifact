#!/usr/bin/env bash
# Experiment B, arms only -- vanilla vs guarded over a horizon of forced
# elections, on the quiet cross-host rig.
#
# WHY THIS RERUN.  The first cross-host arms were measured with netem's DEFAULT
# queue (limit 1000). At 300 tx/s a 200 ms delay needs far more than a thousand
# packets in flight, so the queue overflowed and the rule silently became
# "delay AND heavy loss". Under that rule a delayed FOLLOWER cost 68% of
# throughput, which is not what a delayed follower does: with limit 10000 the
# same follower costs 0.14%, exactly the neutrality Section V-D claims. Every
# number from the first arms run is discarded.
#
# Calibrated on this rig, with limit 10000:
#   clean                       18008 tx / 60 s      290.2 tx/s, 0 failures
#   o3 delayed, FOLLOWER        18008 tx             neutral, -0.14%
#   o3 delayed, LEADER           5663 / 5713 tx      31.6% of clean, -68.4%
#   o3 acquisition, unguarded    4 / 40 forced elections
# so the aggregate the arms should separate is about 0.10 x 0.684 ~ 6.8%,
# against a clean-bracket spread of 0.03%.
#
# Usage: expB_arms.sh [elections] [tps] [delay_ms]
set -u

NE="${1:-40}"; TPS="${2:-300}"; DLY="${3:-200}"
TARGET=3; N=5; W=8
KEY=/tmp/bk.pem; chmod 600 "$KEY" 2>/dev/null
SSH="ssh -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=25 -o BatchMode=yes"
PUB=(x 43.201.32.112 43.200.5.112 52.79.120.204 54.180.116.11 13.125.227.200)
H1=${PUB[1]}; H3=${PUB[3]}; H6=54.180.24.44
IF3=ens5
D=/mnt/d/fabric-d2
OUT=$D/results/expB_arms_$(date +%Y%m%d-%H%M%S); mkdir -p "$OUT"
say(){ echo "[$(date +%H:%M:%S)] $*" | tee -a "$OUT/summary.txt"; }
sshi(){ local i=$1; shift; $SSH ubuntu@${PUB[$i]} "$@"; }
PE="-e CORE_PEER_ADDRESS=peer0.org1.example.com:7051 -e CORE_PEER_MSPCONFIGPATH=/etc/hyperledger/fabric/adminmsp"

# The five log scrapes run in PARALLEL. Sequentially they cost ~12 s, and
# leader_id is called twice per election, so half the wall clock of the first
# run was spent reading logs rather than measuring anything.
leader_id(){
  local i pids=() f
  for i in $(seq 1 $N); do
    ( t=$(sshi $i "sudo docker logs --since 15m orderer 2>&1 | grep -ao 'became leader at term [0-9]*' | tail -1 | grep -ao '[0-9]*\$'"); echo "${t:-0} $i" > /tmp/lid_$i ) &
    pids+=($!)
  done
  for f in "${pids[@]}"; do wait "$f" 2>/dev/null; done
  cat /tmp/lid_1 /tmp/lid_2 /tmp/lid_3 /tmp/lid_4 /tmp/lid_5 2>/dev/null | sort -rn | head -1 | awk '{print ($1>0)?$2:0}'
}
height(){ $SSH ubuntu@$H1 "sudo docker exec $PE peer0 peer channel getinfo -c mychannel 2>/dev/null | grep -ao '\"height\":[0-9]*' | grep -ao '[0-9]*'"; }
# `wait` with no arguments waits for EVERY background job of this shell, and the
# sidecar heal watchdog is one of them -- an infinite loop. The first run of this
# script hung here for hours with no output. Wait on the five PIDs, nothing else.
set_all(){ local i pids=(); for i in $(seq 1 $N); do
  ( sshi $i "sudo docker exec orderer sh -c \"printf '%s' '{\\\"blacklist\\\":$1,\\\"seq\\\":1,\\\"fail_open\\\":false}' > /tmp/bora-advice.json\"" 2>/dev/null ) & pids+=($!)
done; for i in "${pids[@]}"; do wait "$i" 2>/dev/null; done; }
heal(){ local i pids=(); for i in $(seq 1 $N); do
  ( sshi $i 'sudo docker exec -d orderer sh -c "cat /proc/[0-9]*/comm 2>/dev/null | grep -q \"^bora-sidecar\$\" || { rm -f /var/run/raft-advisor.sock; setsid /tmp/bora-sidecar >/tmp/bs.log 2>&1 </dev/null; }"' 2>/dev/null ) & pids+=($!)
done; for i in "${pids[@]}"; do wait "$i" 2>/dev/null; done; }

delay_on(){
  $SSH ubuntu@$H3 "sudo tc qdisc replace dev $IF3 root netem delay ${DLY}ms limit 10000" >/dev/null 2>&1
  local q; q=$($SSH ubuntu@$H3 "tc qdisc show dev $IF3 | grep -o 'netem.*'" 2>/dev/null)
  case "$q" in *"limit 10000"*) say "  netem on: $q" ;;
    *) say "  FATAL netem wrong or absent: '$q'"; exit 1 ;; esac
}
delay_off(){ $SSH ubuntu@$H3 "sudo tc qdisc del dev $IF3 root" >/dev/null 2>&1
  local q; q=$($SSH ubuntu@$H3 "tc qdisc show dev $IF3 | grep -o 'netem.*'" 2>/dev/null)
  [ -n "$q" ] && { say "  WARN netem still present: $q"; return 1; }; say "  netem off"; }
trap 'delay_off >/dev/null 2>&1; $SSH ubuntu@$H6 "sudo docker rm -f caliper-xb" >/dev/null 2>&1; rm -f /tmp/expb_heal' EXIT INT TERM

cal(){ bash $D/alg1/xhost_caliper_net.sh "$TPS" "$2" "$1" "$W" fabric-xhost-ord1.yaml > "$OUT/cal_$1.txt" 2>&1
       grep -aE "^\| $1" "$OUT/cal_$1.txt" | head -1 | tee -a "$OUT/summary.txt"; }
cal_bg(){ bash $D/alg1/xhost_caliper_net.sh "$TPS" "$2" "$1" "$W" fabric-xhost-ord1.yaml > "$OUT/cal_$1.txt" 2>&1 & CALPID=$!; }

say "Experiment B arms: N=$N elections=$NE load=${TPS}tx/s delay=+${DLY}ms limit=10000"
say "output: $OUT"
delay_off >/dev/null 2>&1; set_all "[]"
RUNH=/tmp/expb_heal; touch $RUNH; ( while [ -f $RUNH ]; do heal; sleep 8; done ) & HP=$!
say "  leader=$(leader_id) height=$(height)"

echo "arm,elec,t_pause,t_resume,leader_before,leader_after,target_won" > "$OUT/elections.csv"
echo "arm,success,failed,height_start,height_end,blocks,seconds,target_terms,elections" > "$OUT/arms.csv"

# One election measured on this rig: pause 11 s + settle 6 s + two parallel
# leader reads. Budget 30 s and give caliper the whole span plus warm-up, so the
# load never stops before the elections do -- the first run's caliper round
# ended 45% of the way through each arm and the tail was measured unloaded.
PER=30

run_arm(){ # $1 name  $2 blacklist
  local arm="$1" bl="$2" k L NL won=0 hs he t0 t1 dur
  say "===== arm $arm  (B_t = $bl) ====="
  set_all "$bl"; sleep 2; delay_on
  dur=$(( 60 + NE * PER + 60 ))
  cal_bg "$arm" "$dur"
  say "  caliper up for ${dur}s; 60 s warm-up"
  sleep 60
  set_all "$bl"; t0=$(date +%s); hs=$(height)
  for k in $(seq 1 "$NE"); do
    L=$(leader_id); [ "$L" = 0 ] && L=1
    TP=$(date +%s.%N)
    sshi $L 'sudo docker pause orderer' >/dev/null 2>&1
    sleep 11
    NL=$(leader_id)
    sshi $L 'sudo docker unpause orderer' >/dev/null 2>&1
    TR=$(date +%s.%N); sleep 6
    [ "$NL" = "$TARGET" ] && won=$((won+1))
    echo "$arm,$k,$TP,$TR,$L,$NL,$([ "$NL" = "$TARGET" ] && echo 1 || echo 0)" >> "$OUT/elections.csv"
    say "  e$k: $L -> $NL$([ "$NL" = "$TARGET" ] && echo '   <-- TARGET LEADS')"
  done
  t1=$(date +%s); he=$(height)
  wait $CALPID 2>/dev/null
  delay_off
  local line; line=$(grep -aE "^\| $arm" "$OUT/cal_$arm.txt" | head -1)
  echo "$line" | tee -a "$OUT/summary.txt"
  local succ fail; succ=$(echo "$line" | awk '{print $4}'); fail=$(echo "$line" | awk '{print $6}')
  say "  >>> $arm: success=$succ failed=$fail  height $hs->$he (+$((he-hs)) blocks in $((t1-t0))s)  target led $won/$NE"
  echo "$arm,$succ,$fail,$hs,$he,$((he-hs)),$((t1-t0)),$won,$NE" >> "$OUT/arms.csv"
  set_all "[]"; sleep 3
}

say "===== clean A ====="; cal cleanA 60
run_arm vanilla "[]"
say "===== clean B ====="; cal cleanB 60
run_arm guarded "[$TARGET]"
say "===== clean C ====="; cal cleanC 60

rm -f $RUNH; kill $HP 2>/dev/null || true
delay_off; set_all "[]"
say "===== arms done ====="
cat "$OUT/arms.csv" | tee -a "$OUT/summary.txt"
say "artifacts: $OUT"
