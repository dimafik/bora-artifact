#!/usr/bin/env bash
# Experiment B, cross-host pilot -- what does the guard buy in THROUGHPUT over a
# horizon that contains forced elections?
#
# WHY A SECOND PILOT.  The single-host attempt could not answer the question:
# per-election throughput varied by 26-50%, the two arms drifted 14% apart on a
# growing ledger, and the effect being looked for is 5-11%. The instrument was
# louder than the signal. On this rig four consecutive 60 s runs at 300 tx/s
# returned 290.2 / 290.3 / 290.2 / 290.2 tx/s -- a spread of 0.03%.
#
# WHAT IS DIFFERENT
#   - one orderer per c5.large instance, so orderers do not share a scheduler
#   - the load generator sits on its own c5.2xlarge, so the client never
#     competes with the system under test
#   - c5, not t3: no burst credits to exhaust over a long campaign
#   - clean brackets between arms, so ledger growth and drift are bounded rather
#     than assumed away
#
# PHASES
#   clean1    no delay, no advice                 baseline
#   severity  delay on o3, o3 PINNED as leader    the leader-side cost, here
#   clean2    no delay                            drift check
#   vanilla   delay on o3, B_t = []               o3 may take leadership
#   clean3    no delay                            drift check
#   guarded   delay on o3, B_t = [3]              it may not
#   clean4    no delay                            drift check
#
# Usage: expB_xhost_pilot.sh [elections] [tps] [delay_ms]
set -u

NE="${1:-40}"; TPS="${2:-300}"; DLY="${3:-200}"
TARGET=3; N=5; W=8

KEY=/tmp/bk.pem; chmod 600 "$KEY" 2>/dev/null
SSH="ssh -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=25 -o BatchMode=yes"
PUB=(x 43.201.32.112 43.200.5.112 52.79.120.204 54.180.116.11 13.125.227.200)
H1=${PUB[1]}; H3=${PUB[3]}; H6=54.180.24.44
IF3=ens5
D=/mnt/d/fabric-d2
OUT=$D/results/expB_xhost_$(date +%Y%m%d-%H%M%S); mkdir -p "$OUT"
say(){ echo "[$(date +%H:%M:%S)] $*" | tee -a "$OUT/summary.txt"; }

sshi(){ local i=$1; shift; $SSH ubuntu@${PUB[$i]} "$@"; }
PE="-e CORE_PEER_ADDRESS=peer0.org1.example.com:7051 -e CORE_PEER_MSPCONFIGPATH=/etc/hyperledger/fabric/adminmsp"

# Leadership by highest "became leader at term": the node that most recently
# announced a term is the incumbent. Scraping "Raft leader changed" instead
# returns whatever any node last observed, which lags on a quiet cluster.
# `--tail N` is not safe here: the capacity probes pushed tens of thousands of
# lines through these logs, and the last election scrolled past a 400-line tail
# within minutes. Bound the scrape by TIME instead, and fall back to the whole
# log when a quiet stretch leaves the window empty.
leader_id(){
  local i best=-1 bid=0 t since="${1:-10m}"
  for i in $(seq 1 $N); do
    t=$(sshi $i "sudo docker logs --since $since orderer 2>&1 | grep -ao 'became leader at term [0-9]*' | tail -1 | grep -ao '[0-9]*\$'")
    [ -n "$t" ] && [ "$t" -gt "$best" ] && { best=$t; bid=$i; }
  done
  if [ "$bid" = 0 ] && [ "$since" != "all" ]; then
    for i in $(seq 1 $N); do
      t=$(sshi $i "sudo docker logs orderer 2>&1 | grep -ao 'became leader at term [0-9]*' | tail -1 | grep -ao '[0-9]*\$'")
      [ -n "$t" ] && [ "$t" -gt "$best" ] && { best=$t; bid=$i; }
    done
  fi
  echo "$bid"
}
height(){ $SSH ubuntu@$H1 "sudo docker exec $PE peer0 peer channel getinfo -c mychannel 2>/dev/null | grep -ao '\"height\":[0-9]*' | grep -ao '[0-9]*'"; }
set_all(){ local i; for i in $(seq 1 $N); do
  sshi $i "sudo docker exec orderer sh -c \"printf '%s' '{\\\"blacklist\\\":$1,\\\"seq\\\":1,\\\"fail_open\\\":false}' > /tmp/bora-advice.json\"" 2>/dev/null
done; }
heal(){ local i; for i in $(seq 1 $N); do
  sshi $i 'sudo docker exec -d orderer sh -c "cat /proc/[0-9]*/comm 2>/dev/null | grep -q \"^bora-sidecar\$\" || { rm -f /var/run/raft-advisor.sock; setsid /tmp/bora-sidecar >/tmp/bs.log 2>&1 </dev/null; }"' 2>/dev/null || true
done; }

# netem on the host interface: the orderer runs --network host, so this is the
# orderer's own egress. Verified after every change -- a silently absent rule is
# how the first cross-host detection feeds ended up with no attack in them.
delay_on(){
  $SSH ubuntu@$H3 "sudo tc qdisc replace dev $IF3 root netem delay ${DLY}ms limit 10000" >/dev/null 2>&1
  local q; q=$($SSH ubuntu@$H3 "tc qdisc show dev $IF3 | grep -o 'netem.*'" 2>/dev/null)
  [ -z "$q" ] && { say "  FATAL netem did not apply"; exit 1; }
  say "  netem on: $q"
}
delay_off(){
  $SSH ubuntu@$H3 "sudo tc qdisc del dev $IF3 root" >/dev/null 2>&1
  local q; q=$($SSH ubuntu@$H3 "tc qdisc show dev $IF3 | grep -o 'netem.*'" 2>/dev/null)
  [ -n "$q" ] && { say "  WARN netem still present: $q"; return 1; }
  say "  netem off"
}
trap 'delay_off >/dev/null 2>&1; $SSH ubuntu@$H6 "sudo docker rm -f caliper-xb" >/dev/null 2>&1; rm -f /tmp/expb_heal' EXIT INT TERM

caliper(){ # $1=label $2=seconds ; blocking
  bash $D/alg1/xhost_caliper.sh "$TPS" "$2" "$1" "$W" > "$OUT/cal_$1.txt" 2>&1
  grep -aE "^\| $1" "$OUT/cal_$1.txt" | head -1 | tee -a "$OUT/summary.txt"
}
caliper_bg(){ # $1=label $2=seconds
  bash $D/alg1/xhost_caliper.sh "$TPS" "$2" "$1" "$W" > "$OUT/cal_$1.txt" 2>&1 &
  CALPID=$!
}

hs_start(){ $SSH ubuntu@$H1 "touch /tmp/hs.on; nohup bash -c 'while [ -f /tmp/hs.on ]; do h=\$(sudo docker exec $PE peer0 peer channel getinfo -c mychannel 2>/dev/null | grep -ao \"\\\"height\\\":[0-9]*\" | grep -ao \"[0-9]*\"); echo \"\$(date +%s.%N),\${h:-NA}\"; done' > /tmp/height.csv 2>/dev/null & echo started" >/dev/null 2>&1; }
hs_stop(){ $SSH ubuntu@$H1 'rm -f /tmp/hs.on' >/dev/null 2>&1; sleep 1; $SSH ubuntu@$H1 'cat /tmp/height.csv' > "$OUT/height_$1.csv" 2>/dev/null; local n; n=$(wc -l < "$OUT/height_$1.csv"); say "  height samples ($1): $n"; }

say "Experiment B cross-host pilot: N=$N elections=$NE load=${TPS}tx/s delay=+${DLY}ms target=orderer$TARGET"
say "output: $OUT"
delay_off >/dev/null 2>&1
set_all "[]"
RUNH=/tmp/expb_heal; touch $RUNH; ( while [ -f $RUNH ]; do heal; sleep 5; done ) & HP=$!
say "  starting leader: $(leader_id), height $(height)"

# --------------------------------------------------------------- clean 1
say "===== clean1 (no delay, no advice) ====="
caliper clean1 60

# --------------------------------------------------------------- severity
say "===== severity: pin orderer$TARGET as leader, then delay it ====="
say "  pinning with the delay OFF -- a delayed node wins less often, so pinning under attack fights itself"
pin_ok=0
for k in $(seq 1 40); do
  L=$(leader_id)
  [ "$L" = "$TARGET" ] && { say "  attempt $k: orderer$TARGET is leader"; pin_ok=1; break; }
  [ "$L" = 0 ] && L=1
  sshi $L 'sudo docker restart orderer' >/dev/null 2>&1
  sleep 14; heal
  [ $((k % 5)) = 0 ] && say "  ...$k tries, leader=$(leader_id)"
done
if [ "$pin_ok" = 1 ]; then
  delay_on
  sleep 5
  LL=$(leader_id); say "  leader under delay: $LL (must be $TARGET)"
  if [ "$LL" = "$TARGET" ]; then caliper severity 60; else say "  o3 was deposed before the run; severity skipped"; fi
  delay_off
else
  say "  *** could not pin orderer$TARGET in 40 attempts; severity skipped"
fi

# --------------------------------------------------------------- clean 2
say "===== clean2 (drift check) ====="
caliper clean2 60

# ------------------------------------------------------------------- arms
run_arm(){ # $1=name $2=blacklist
  local arm="$1" bl="$2" k L NL won=0 hs he t0 t1 dur
  say "===== arm $arm  (B_t = $bl) ====="
  set_all "$bl"; sleep 2
  delay_on
  dur=$(( 60 + NE * 24 + 30 ))
  hs_start
  caliper_bg "$arm" "$dur"
  say "  caliper up for ${dur}s; 60s warm-up before the first election"
  sleep 60
  set_all "$bl"
  t0=$(date +%s); hs=$(height)
  echo "arm,elec,t_pause,t_resume,leader_before,leader_after,target_won" >> "$OUT/elections.csv"
  for k in $(seq 1 "$NE"); do
    set_all "$bl"
    L=$(leader_id); [ "$L" = 0 ] && L=1
    TP=$(date +%s.%N)
    sshi $L 'sudo docker pause orderer' >/dev/null 2>&1
    sleep 11
    NL=$(leader_id)
    sshi $L 'sudo docker unpause orderer' >/dev/null 2>&1
    TR=$(date +%s.%N)
    sleep 6; heal
    [ "$NL" = "$TARGET" ] && won=$((won+1))
    echo "$arm,$k,$TP,$TR,$L,$NL,$([ "$NL" = "$TARGET" ] && echo 1 || echo 0)" >> "$OUT/elections.csv"
    say "  e$k: $L -> $NL$([ "$NL" = "$TARGET" ] && echo '   <-- TARGET LEADS')"
  done
  t1=$(date +%s); he=$(height)
  wait $CALPID 2>/dev/null
  hs_stop "$arm"
  delay_off
  local secs=$((t1-t0)) blocks=$(( ${he:-0} - ${hs:-0} ))
  say "  >>> arm $arm: height $hs -> $he (+$blocks blocks in ${secs}s), target led $won/$NE"
  grep -aE "^\| $arm" "$OUT/cal_$arm.txt" | head -1 | tee -a "$OUT/summary.txt"
  echo "$arm,$hs,$he,$blocks,$secs,$won,$NE" >> "$OUT/arms.csv"
  set_all "[]"; sleep 3
}

echo "arm,height_start,height_end,blocks,seconds,target_terms,elections" > "$OUT/arms.csv"
run_arm vanilla "[]"
say "===== clean3 (drift check) ====="
caliper clean3 60
run_arm guarded "[$TARGET]"
say "===== clean4 (drift check) ====="
caliper clean4 60

rm -f $RUNH; kill $HP 2>/dev/null || true
delay_off; set_all "[]"
say "===== pilot done ====="
cat "$OUT/arms.csv" | tee -a "$OUT/summary.txt"
say "artifacts: $OUT"
