#!/usr/bin/env bash
# 11_potency, re-measured on the quiet cross-host rig.
#
# WHAT IT ASKS.  The white-box study says every detector we tried falls to an
# adaptive adversary. This asks the next question: the evasion sequences that
# beat the detector -- what do they actually do to the ordering service? The
# original answer (artifact 11_potency) was "nothing measurable", and it is the
# reason Theorem 1's containment is worth having. It sits in the response letter
# rather than the body because of how it was measured, not what it found:
#
#   custom loadgen.sh, not Caliper   Caliper was not installed on that rig
#   noise too large to trust -0.7 to -4.1%
#   unequal sample counts            --waitForEvent tied workers to the delay
#
# This rig fixes all three: Caliper with 8 workers on a dedicated c5.2xlarge,
# clean-bracket spread 0.069% over an hour, and a fixed offered rate so every
# condition submits the same volume.
#
# AND ONE CORRECTNESS FIX.  The original injected the tracks with
#   tc qdisc replace dev eth0 root netem delay ${d}ms
# -- no limit, so netem's default queue of 1000 packets. At the m500 scale a
# 500 ms delay overflows that queue above ~2000 pkt/s and netem starts DROPPING,
# which makes the injected fault "delay AND loss" rather than delay. Every
# qdisc here carries limit 10000 and is verified after it is set.
#
# TWO ADAPTATIONS, both disclosed:
#   N=5 not 7   this rig has five orderers; the tracks' first five columns keep
#               the design property intact -- every orderer at the same ~500 ms
#               marginal, only orderer3's autocorrelation varying 0.026 -> 0.886
#   port filter the orderers run --network host, so a root qdisc would delay the
#               peer and ssh as well. A prio band filtered on sport 7050/7053
#               delays consensus traffic only: measured 304 ms on orderer3:7050
#               and 0.2 ms on peer0.org2:7051 with the same rule standing
#
# Usage: potency_xhost.sh [reps] [seconds] [tps]
set -u
REPS="${1:-3}"; SECS="${2:-180}"; TPS="${3:-150}"; W=8; POOL=500; TICK=0.15
KEY=/tmp/bk.pem; chmod 600 "$KEY" 2>/dev/null
SSH="ssh -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=30 -o BatchMode=yes"
SCP="scp -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=30 -q"
PUB=(x 3.34.1.207 13.124.149.80 13.209.43.120 15.164.234.3 54.180.32.6)
H1=${PUB[1]}; H6=43.201.115.162
N=5
D=/mnt/d/fabric-d2
TR=$D/results/potency_tracks
CONDS=(healthy_white pgd_rho_0.0 pgd_rho_0.3 pgd_rho_0.6 pgd_rho_0.8 attack_class_ar1)
NC=${#CONDS[@]}
OUT=$D/results/potency_xhost_$(date +%Y%m%d-%H%M%S); mkdir -p "$OUT"
TAG=$(basename "$OUT" | sed 's/potency_xhost_//')
say(){ echo "[$(date +%H:%M:%S)] $*" | tee -a "$OUT/summary.txt"; }
sshi(){ local i=$1; shift; $SSH ubuntu@${PUB[$i]} "$@"; }
PE1="-e CORE_PEER_ADDRESS=peer0.org1.example.com:7051 -e CORE_PEER_MSPCONFIGPATH=/etc/hyperledger/fabric/adminmsp"
ADDH="--add-host orderer.example.com:172.31.39.233 --add-host orderer2.example.com:172.31.44.2 \
--add-host orderer3.example.com:172.31.37.115 --add-host orderer4.example.com:172.31.46.160 \
--add-host orderer5.example.com:172.31.39.145 \
--add-host peer0.org1.example.com:172.31.39.233 --add-host peer0.org2.example.com:172.31.44.2"

height(){ $SSH ubuntu@$H1 "sudo docker exec $PE1 peer0 peer channel getinfo -c mychannel 2>/dev/null | grep -ao '\"height\":[0-9]*' | grep -ao '[0-9]*'"; }

# --- delay plumbing -------------------------------------------------------
tc_up(){   # prio root + a netem band filtered to the consensus ports
  local i pids=() p
  for i in $(seq 1 $N); do
    ( sshi $i "sudo tc qdisc del dev ens5 root 2>/dev/null
       sudo tc qdisc add dev ens5 root handle 1: prio bands 3
       sudo tc qdisc add dev ens5 parent 1:3 handle 30: netem delay 1ms limit 10000
       sudo tc filter add dev ens5 protocol ip parent 1:0 prio 1 u32 match ip sport 7050 0xffff flowid 1:3
       sudo tc filter add dev ens5 protocol ip parent 1:0 prio 1 u32 match ip sport 7053 0xffff flowid 1:3" >/dev/null 2>&1 ) & pids+=($!)
  done
  for p in "${pids[@]}"; do wait "$p" 2>/dev/null; done
  local ok=0
  for i in $(seq 1 $N); do
    sshi $i "tc qdisc show dev ens5 | grep -q 'limit 10000'" 2>/dev/null && ok=$((ok+1))
  done
  say "  tc band installed on $ok/$N"; [ "$ok" = "$N" ] || exit 1
}
tc_down(){ local i; for i in $(seq 1 $N); do ( sshi $i 'sudo tc qdisc del dev ens5 root' >/dev/null 2>&1 ) & done; wait; }
tc_flat(){ local i pids=() p    # every orderer at 1 ms: the no-delay reference
  for i in $(seq 1 $N); do
    ( sshi $i "sudo tc qdisc change dev ens5 parent 1:3 handle 30: netem delay 1ms limit 10000" >/dev/null 2>&1 ) & pids+=($!)
  done; for p in "${pids[@]}"; do wait "$p" 2>/dev/null; done; }

# The replay runs ON each host. Driving it over ssh would put a connection
# handshake in a 0.15 s loop -- 1200 of them per round, which is the load.
stage_tracks(){
  local c i
  for i in $(seq 1 $N); do
    $SCP "$D/alg1/potency_replay.sh" ubuntu@${PUB[$i]}:/tmp/replay.sh
    sshi $i 'chmod +x /tmp/replay.sh' >/dev/null 2>&1
  done
  for c in "${CONDS[@]}"; do
    for i in $(seq 1 $N); do
      awk -F, -v k=$i '{printf "%.3f\n", $k}' "$TR/$c.csv" > /tmp/trk_${c}_$i.txt
      $SCP /tmp/trk_${c}_$i.txt ubuntu@${PUB[$i]}:/tmp/trk_${c}.txt
    done
  done
  local n=0
  for i in $(seq 1 $N); do sshi $i 'test -x /tmp/replay.sh' 2>/dev/null && n=$((n+1)); done
  say "  replay script on $n/$N hosts; ${#CONDS[@]} tracks x $N columns staged"
  [ "$n" = "$N" ] || exit 1
}
replay_start(){ local c=$1 i pids=() p
  for i in $(seq 1 $N); do
    ( sshi $i "sudo rm -f /tmp/replay.stop /tmp/replay.err; sudo nohup /tmp/replay.sh /tmp/trk_${c}.txt $TICK >/dev/null 2>&1 &" >/dev/null 2>&1 ) & pids+=($!)
  done
  for p in "${pids[@]}"; do wait "$p" 2>/dev/null; done
  sleep 6
  # A replay that is not moving the qdisc is the failure this experiment cannot
  # survive quietly: the run completes, the numbers look plausible, and every
  # condition turns out to have been measured at one fixed delay. The first
  # attempt failed exactly that way -- three levels of quoting delivered tc a
  # literal \486.324ms, tc answered `Illegal "latency"`, and the qdisc never moved.
  local a b moved=0
  for i in $(seq 1 $N); do
    a=$(sshi $i "tc qdisc show dev ens5 | grep -o 'delay [0-9.]*ms'" 2>/dev/null)
    sleep 0.4
    b=$(sshi $i "tc qdisc show dev ens5 | grep -o 'delay [0-9.]*ms'" 2>/dev/null)
    [ "$a" != "$b" ] && moved=$((moved+1))
  done
  [ "$moved" -ge 3 ] || { say "  *** replay not moving the qdisc ($moved/$N changed) -- aborting"; exit 1; }
}
replay_stop(){ local i pids=() p
  for i in $(seq 1 $N); do
    ( sshi $i 'sudo touch /tmp/replay.stop; sleep 0.5; sudo pkill -f replay.sh 2>/dev/null' >/dev/null 2>&1 ) & pids+=($!)
  done
  for p in "${pids[@]}"; do wait "$p" 2>/dev/null; done
  tc_flat; }

bench(){ $SSH ubuntu@$H6 "cat > /home/ubuntu/caliper-workspace/benchmarks/_pot.yaml" <<YML
test:
  name: pot
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
cal(){ bench "$1" "$2"
  $SSH ubuntu@$H6 "sudo docker rm -f pot-$TAG >/dev/null 2>&1
    sudo docker run --rm --name pot-$TAG $ADDH \
      -v /home/ubuntu/caliper-workspace:/hyperledger/caliper/workspace \
      -v /home/ubuntu/organizations:/cryptoMount \
      -e CALIPER_BIND_SUT=fabric:fabric-gateway \
      -e CALIPER_BENCHCONFIG=benchmarks/_pot.yaml \
      -e CALIPER_NETWORKCONFIG=networks/fabric-xhost-ord1.yaml \
      -e CALIPER_FLOW_ONLY_TEST=true \
      hyperledger/caliper:0.6.0 launch manager > /tmp/pot_$1.log 2>&1
    grep -aE '^\| $1' /tmp/pot_$1.log | head -1" > "$OUT/line_$1.txt" 2>&1
  cat "$OUT/line_$1.txt"
}

trap 'replay_stop >/dev/null 2>&1; tc_down; $SSH ubuntu@$H6 "sudo docker rm -f pot-$TAG" >/dev/null 2>&1' EXIT INT TERM

say "potency re-measure: reps=$REPS secs=${SECS}s tps=$TPS workers=$W  (N=$N, port-filtered netem, limit 10000)"
say "output: $OUT"
stage_tracks
tc_up
# Caliper's report line is
#   | name | Succ | Fail | Send Rate | Max Latency | Min Latency | Avg Latency | Throughput |
# i.e. awk fields $4 $6 $8 $10 $12 $14 $16.  An earlier version of this
# script read $10 into a column it called lat_avg and $12 into one it called
# lat_max, so the file said max < avg and never carried the average at all.
echo "rep,position,condition,success,failed,send_rate,lat_max,lat_min,lat_avg,throughput,h0,h1,blocks" > "$OUT/results.csv"

for rep in $(seq 1 "$REPS"); do
  say "########## rep $rep ##########"
  for pos in $(seq 0 $((NC-1))); do
    idx=$(( (pos + rep - 1) % NC ))
    c=${CONDS[$idx]}
    lab="r${rep}_p${pos}_${c//./_}"
    replay_start "$c"
    h0=$(height)
    L=$(cal "$lab" "$SECS")
    h1=$(height)
    replay_stop
    s=$(echo "$L" | awk '{print $4}');  f=$(echo "$L"  | awk '{print $6}')
    sr=$(echo "$L" | awk '{print $8}'); lmx=$(echo "$L" | awk '{print $10}')
    lmn=$(echo "$L" | awk '{print $12}'); lav=$(echo "$L" | awk '{print $14}')
    t=$(echo "$L" | awk '{print $16}')
    say "  pos$pos $c: succ=${s:-NA} fail=${f:-NA} tput=${t:-NA} lat avg=${lav:-NA} max=${lmx:-NA} min=${lmn:-NA} blocks=$((h1-h0))"
    echo "$rep,$pos,$c,${s:-NA},${f:-NA},${sr:-NA},${lmx:-NA},${lmn:-NA},${lav:-NA},${t:-NA},$h0,$h1,$((h1-h0))" >> "$OUT/results.csv"
  done
done

tc_down
say "===== done ====="
cat "$OUT/results.csv" | tee -a "$OUT/summary.txt"
say "artifacts: $OUT"
