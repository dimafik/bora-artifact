#!/usr/bin/env bash
# Experiment B, the campaign. What does the guard buy in committed throughput
# over a horizon that contains forced elections?
#
# Section V-D answers R2-5 with two separately measured things: how often the
# unguarded arm seats the degraded orderer (21 of 240 at +200 ms) and what a
# degraded leader costs (65%). The paper reports them side by side rather than
# as a product; this run asked whether the combined effect could be measured
# directly instead.  It could not -- see the README.
#
# CALIBRATED ON THIS RIG, all with netem limit 10000:
#   clean baseline              18008 tx / 60 s   290.2 tx/s, 0 failures
#   o3 delayed, FOLLOWER        18008 tx          neutral, -0.14%
#   o3 delayed, LEADER           5663 / 5713 tx   31.6% of clean, -68.4%
#   o3 acquisition, unguarded    4 / 40 forced elections
# so the arms should separate by about 0.10 x 0.684 ~ 6.8%, against a
# clean-bracket spread of 0.03%.
#
# WHAT THIS RUN DOES DIFFERENTLY FROM EVERY EARLIER ATTEMPT
#   netem limit 10000        the default 1000 drops packets at this rate and
#                            injects "delay AND loss", which is a different fault
#   bounded workload         updateAsset over a fixed key pool; createAsset grew
#                            the world state until the baseline halved mid-campaign
#   arm order alternated     seed 1 runs vanilla first, seed 2 guarded first, so
#                            a drift with time cannot masquerade as an arm effect
#   clean brackets           before and after every arm, so drift is measured
#                            rather than assumed absent
#   per-run container names  a late EXIT trap from a killed run used to delete
#                            the live run's container and every result came back
#                            empty with no error
#   wait on explicit PIDs    a bare `wait` also waits for the sidecar watchdog,
#                            an infinite loop; one run hung on it for 5h40m
#
# Usage: expB_campaign.sh [seeds] [elections] [tps] [delay_ms]
set -u

SEEDS="${1:-2}"; NE="${2:-100}"; TPS="${3:-300}"; DLY="${4:-200}"
TARGET=3; N=5; W=8; POOL=500; PER=28

KEY=/tmp/bk.pem; chmod 600 "$KEY" 2>/dev/null
SSH="ssh -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=30 -o BatchMode=yes"
PUB=(x 3.34.1.207 13.124.149.80 13.209.43.120 15.164.234.3 54.180.32.6)
H1=${PUB[1]}; H3=${PUB[3]}; H6=43.201.115.162
IF3=ens5
D=/mnt/d/fabric-d2
OUT=$D/results/expB_camp_$(date +%Y%m%d-%H%M%S); mkdir -p "$OUT"
TAG=$(basename "$OUT" | sed 's/expB_camp_//')
say(){ echo "[$(date +%H:%M:%S)] $*" | tee -a "$OUT/summary.txt"; }
sshi(){ local i=$1; shift; $SSH ubuntu@${PUB[$i]} "$@"; }
PE1="-e CORE_PEER_ADDRESS=peer0.org1.example.com:7051 -e CORE_PEER_MSPCONFIGPATH=/etc/hyperledger/fabric/adminmsp"
ADDH="--add-host orderer.example.com:172.31.39.233 --add-host orderer2.example.com:172.31.44.2 \
--add-host orderer3.example.com:172.31.37.115 --add-host orderer4.example.com:172.31.46.160 \
--add-host orderer5.example.com:172.31.39.145 \
--add-host peer0.org1.example.com:172.31.39.233 --add-host peer0.org2.example.com:172.31.44.2"

leader_id(){
  local i pids=() p
  for i in $(seq 1 $N); do
    ( t=$(sshi $i "sudo docker logs --since 20m orderer 2>&1 | grep -ao 'became leader at term [0-9]*' | tail -1 | grep -ao '[0-9]*\$'"); echo "${t:-0} $i" > /tmp/cl_$i ) &
    pids+=($!)
  done
  for p in "${pids[@]}"; do wait "$p" 2>/dev/null; done
  cat /tmp/cl_1 /tmp/cl_2 /tmp/cl_3 /tmp/cl_4 /tmp/cl_5 2>/dev/null | sort -rn | head -1 | awk '{print ($1>0)?$2:0}'
}
height(){ $SSH ubuntu@$H1 "sudo docker exec $PE1 peer0 peer channel getinfo -c mychannel 2>/dev/null | grep -ao '\"height\":[0-9]*' | grep -ao '[0-9]*'"; }
set_all(){ local i pids=() p; for i in $(seq 1 $N); do
  ( sshi $i "sudo docker exec orderer sh -c \"printf '%s' '{\\\"blacklist\\\":$1,\\\"seq\\\":1,\\\"fail_open\\\":false}' > /tmp/bora-advice.json\"" 2>/dev/null ) & pids+=($!)
done; for p in "${pids[@]}"; do wait "$p" 2>/dev/null; done; }
heal(){ local i pids=() p; for i in $(seq 1 $N); do
  ( sshi $i 'sudo docker exec -d orderer sh -c "cat /proc/[0-9]*/comm 2>/dev/null | grep -q \"^bora-sidecar\$\" || { rm -f /var/run/raft-advisor.sock; setsid /tmp/bora-sidecar >/tmp/bs.log 2>&1 </dev/null; }"' 2>/dev/null ) & pids+=($!)
done; for p in "${pids[@]}"; do wait "$p" 2>/dev/null; done; }

delay_on(){
  $SSH ubuntu@$H3 "sudo tc qdisc replace dev $IF3 root netem delay ${DLY}ms limit 10000" >/dev/null 2>&1
  local q; q=$($SSH ubuntu@$H3 "tc qdisc show dev $IF3 | grep -o 'netem.*'" 2>/dev/null)
  case "$q" in *"limit 10000"*) say "  netem on: $q" ;;
    *) say "  FATAL netem wrong or absent: '$q'"; exit 1 ;; esac
}
delay_off(){
  $SSH ubuntu@$H3 "sudo tc qdisc del dev $IF3 root" >/dev/null 2>&1
  local q; q=$($SSH ubuntu@$H3 "tc qdisc show dev $IF3 | grep -o 'netem.*'" 2>/dev/null)
  [ -n "$q" ] && { say "  *** netem survived removal: $q"; return 1; }; return 0
}
trap 'delay_off >/dev/null 2>&1; $SSH ubuntu@$H6 "sudo docker rm -f cal-$TAG" >/dev/null 2>&1; rm -f /tmp/camp_heal' EXIT INT TERM

bench(){ $SSH ubuntu@$H6 "cat > /home/ubuntu/caliper-workspace/benchmarks/_camp.yaml" <<YML
test:
  name: camp
  workers: {number: $W}
  rounds:
    - label: $1
      txDuration: $2
      rateControl: {type: fixed-rate, opts: {tps: $TPS}}
      workload:
        module: workload/updateAsset.js
        arguments: {poolSize: $POOL}
YML
}
cal_run(){  # $1 label $2 seconds ; blocking
  bench "$1" "$2"
  $SSH ubuntu@$H6 "sudo docker rm -f cal-$TAG >/dev/null 2>&1
    sudo docker run --rm --name cal-$TAG $ADDH \
      -v /home/ubuntu/caliper-workspace:/hyperledger/caliper/workspace \
      -v /home/ubuntu/organizations:/cryptoMount \
      -e CALIPER_BIND_SUT=fabric:fabric-gateway \
      -e CALIPER_BENCHCONFIG=benchmarks/_camp.yaml \
      -e CALIPER_NETWORKCONFIG=networks/fabric-xhost-ord1.yaml \
      -e CALIPER_FLOW_ONLY_TEST=true \
      hyperledger/caliper:0.6.0 launch manager > /tmp/camp_$1.log 2>&1
    grep -aE '^\| $1' /tmp/camp_$1.log | head -1" > "$OUT/line_$1.txt" 2>&1
  cat "$OUT/line_$1.txt"
}
cal_bg(){ bench "$1" "$2"
  ( $SSH ubuntu@$H6 "sudo docker rm -f cal-$TAG >/dev/null 2>&1
      sudo docker run --rm --name cal-$TAG $ADDH \
        -v /home/ubuntu/caliper-workspace:/hyperledger/caliper/workspace \
        -v /home/ubuntu/organizations:/cryptoMount \
        -e CALIPER_BIND_SUT=fabric:fabric-gateway \
        -e CALIPER_BENCHCONFIG=benchmarks/_camp.yaml \
        -e CALIPER_NETWORKCONFIG=networks/fabric-xhost-ord1.yaml \
        -e CALIPER_FLOW_ONLY_TEST=true \
        hyperledger/caliper:0.6.0 launch manager > /tmp/camp_$1.log 2>&1
      grep -aE '^\| $1' /tmp/camp_$1.log | head -1" > "$OUT/line_$1.txt" 2>&1 ) &
  CALPID=$!
}

bracket(){ say "  --- bracket $1 ---"; delay_off; sleep 4; cal_run "$1" 60 | tee -a "$OUT/summary.txt"; }

run_arm(){ # $1 label  $2 blacklist  $3 seed
  local lab="$1" bl="$2" sd="$3" k L NL won=0 hs he t0 t1 dur
  say "===== seed $sd arm $lab  (B_t = $bl) ====="
  set_all "$bl"; sleep 2; delay_on
  dur=$(( 60 + NE * PER + 90 ))
  cal_bg "$lab" "$dur"
  say "  caliper up ${dur}s; 60 s warm-up"
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
    echo "$sd,$lab,$k,$TP,$TR,$L,$NL,$([ "$NL" = "$TARGET" ] && echo 1 || echo 0)" >> "$OUT/elections.csv"
    [ $((k % 10)) = 0 ] && say "  e$k/$NE (target led $won so far)"
  done
  t1=$(date +%s); he=$(height)
  wait $CALPID 2>/dev/null
  delay_off
  local line succ fail tput
  line=$(cat "$OUT/line_$lab.txt" 2>/dev/null)
  succ=$(echo "$line" | awk '{print $4}'); fail=$(echo "$line" | awk '{print $6}'); tput=$(echo "$line" | awk '{print $16}')
  say "  >>> seed $sd $lab: succ=${succ:-NA} fail=${fail:-NA} tput=${tput:-NA}  height $hs->$he (+$((he-hs)))  target led $won/$NE"
  echo "$sd,$lab,${succ:-NA},${fail:-NA},${tput:-NA},$hs,$he,$((he-hs)),$((t1-t0)),$won,$NE" >> "$OUT/arms.csv"
  set_all "[]"; sleep 3
}

say "Experiment B campaign: seeds=$SEEDS elections=$NE load=${TPS}tx/s delay=+${DLY}ms pool=$POOL"
say "output: $OUT"
delay_off >/dev/null 2>&1; set_all "[]"
RUNH=/tmp/camp_heal; touch $RUNH; ( while [ -f $RUNH ]; do heal; sleep 10; done ) & HP=$!
say "  leader=$(leader_id) height=$(height)"
echo "seed,arm,elec,t_pause,t_resume,leader_before,leader_after,target_won" > "$OUT/elections.csv"
echo "seed,arm,success,failed,throughput,height_start,height_end,blocks,seconds,target_terms,elections" > "$OUT/arms.csv"

for s in $(seq 1 "$SEEDS"); do
  say "########## seed $s ##########"
  bracket "s${s}_pre"
  # Alternate which arm goes first. If the rig drifts with time, a fixed order
  # turns that drift into an apparent arm effect; alternating cancels it.
  if [ $((s % 2)) = 1 ]; then
    run_arm "s${s}_vanilla" "[]"        "$s"
    bracket "s${s}_mid"
    run_arm "s${s}_guarded" "[$TARGET]" "$s"
  else
    run_arm "s${s}_guarded" "[$TARGET]" "$s"
    bracket "s${s}_mid"
    run_arm "s${s}_vanilla" "[]"        "$s"
  fi
  bracket "s${s}_post"
done

rm -f $RUNH; kill $HP 2>/dev/null || true
delay_off; set_all "[]"
say "===== campaign done ====="
cat "$OUT/arms.csv" | tee -a "$OUT/summary.txt"
say "artifacts: $OUT"
