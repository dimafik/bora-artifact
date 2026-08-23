#!/usr/bin/env bash
# R2-5: what does a degraded LEADER cost, versus a degraded follower?
#
# WHY. Reviewer 2 wrote that the demonstrated practical gain is narrow: BORA is
# throughput-neutral under follower delay, so the only measurable benefit is a
# lower leadership-acquisition rate for the target. The manuscript's answer is
# the sentence "a slow leader throttles the channel however it came to hold the
# term" -- and that sentence is not backed by a measurement. Section V-C measures
# delay on a FOLLOWER (15-25% loss). Nobody measured delay on the LEADER.
#
# If a degraded leader costs materially more than a degraded follower, then
# keeping it out of the leader role has a quantified system-level benefit and
# R2-5 is answered with data. If it costs about the same, the reviewer is right
# and we must say so. Either way the number belongs in the paper.
#
# METHOD. Committed throughput is taken from ledger block-height growth over a
# fixed window, the same confirmed-commit basis Section V-C uses, rather than
# from the offered send rate.
#
#   Arm N  no delay            (ceiling for this host)
#   Arm F  +DLY on a follower  (reproduces Section V-C)
#   Arm L  +DLY on the leader  (the missing measurement)
#
# A delayed leader may be deposed by vanilla Raft mid-window, which would end the
# condition we are trying to measure. Leadership is therefore sampled before and
# after each window and reported; a window whose leader changed is flagged rather
# than silently averaged in.
#
# Usage: r25_leader_cost.sh [tps] [window_s] [delay_ms] [repeats]
set -u

TPS="${1:-300}"; WIN="${2:-120}"; DLY="${3:-500}"; REPS="${4:-2}"
N=5

D=/mnt/d/fabric-d2
R=$D/results
WS=$D/caliper-workspace
CRYPTO=$D/fabric-samples/test-network/organizations
export PATH=/tmp/bin:$D/fabric-samples/bin-linux/bin:/usr/local/bin:/usr/bin:/bin

host(){ [ "$1" = 1 ] && echo orderer || echo "orderer$1"; }
cont(){ echo "$(host $1).example.com"; }
ORD=(); for i in $(seq 1 $N); do ORD+=("$(cont $i)"); done

OUT="$R/r25_$(date +%Y%m%d-%H%M%S)"; mkdir -p "$OUT"
echo "R2-5 leader-cost: tps=$TPS window=${WIN}s delay=${DLY}ms reps=$REPS" | tee "$OUT/timeline.txt"

# Highest term seen wins; a node that never logged "became leader" is not it.
leader_id(){ local b=-1 bid=0 id o t
  for id in $(seq 1 $N); do o=$(cont $id)
    t=$(docker logs --tail 300 "$o" 2>&1 | grep -ao "became leader at term [0-9]*" | tail -1 | grep -ao "[0-9]*$")
    [ -n "${t:-}" ] && [ "$t" -gt "$b" ] && { b=$t; bid=$id; }
  done; echo "$bid"; }

# Confirmed commits: ledger height, read from an orderer's own block store via
# the admin endpoint is awkward, so use a peer's channel info.
height(){ docker exec cli sh -c \
  'peer channel getinfo -c mychannel 2>/dev/null' 2>/dev/null \
  | grep -ao '"height":[0-9]*' | grep -ao '[0-9]*$'; }

gen_bench(){ mkdir -p "$WS/benchmarks"; cat > "$WS/benchmarks/_r25.yaml" <<YML
test:
  name: r25-$1
  workers: {number: 4}
  rounds:
    - label: r25-$1
      txDuration: $((WIN + 90))
      rateControl: {type: fixed-rate, opts: {tps: $1}}
      workload: {module: workload/createAsset.js}
YML
}
start_load(){ gen_bench "$TPS"
  docker rm -f caliper-r25 >/dev/null 2>&1 || true
  docker run --rm --name caliper-r25 --network fabric_test \
    -v "$WS:/hyperledger/caliper/workspace" -v "$CRYPTO:/cryptoMount" \
    --add-host=host.docker.internal:host-gateway \
    -e CALIPER_BIND_SUT=fabric:fabric-gateway \
    -e CALIPER_BENCHCONFIG=benchmarks/_r25.yaml \
    -e CALIPER_NETWORKCONFIG=networks/fabric-5node.yaml \
    -e CALIPER_FLOW_ONLY_TEST=true \
    hyperledger/caliper:0.6.0 launch manager > "$OUT/caliper_$1.log" 2>&1 &
  sleep 45; }                      # warm-up before the measurement window opens
stop_load(){ docker rm -f caliper-r25 >/dev/null 2>&1 || true; }

netem_on(){ docker rm -f pumba-r25 >/dev/null 2>&1
  docker run -d --name pumba-r25 -v /var/run/docker.sock:/var/run/docker.sock \
    gaiaadm/pumba:latest --log-level warning netem --tc-image gaiadocker/iproute2 \
    --duration $((WIN + 180))s delay --time "$DLY" "$1" >/dev/null 2>&1; sleep 5; }
netem_off(){ docker rm -f pumba-r25 >/dev/null 2>&1; sleep 3; }

cleanup(){ stop_load; netem_off; }
trap cleanup EXIT INT TERM

echo "arm,rep,target,leader_before,leader_after,leader_changed,h0,h1,blocks,secs,blocks_per_s" > "$OUT/results.csv"

run_arm(){                          # $1=label  $2=container to delay ("" = none)
  local arm="$1" tgt="${2:-}" rep h0 h1 lb la ch secs
  for rep in $(seq 1 "$REPS"); do
    [ -n "$tgt" ] && netem_on "$tgt" || netem_off
    start_load
    lb=$(leader_id); h0=$(height); local t0=$(date +%s)
    sleep "$WIN"
    h1=$(height); local t1=$(date +%s); la=$(leader_id)
    stop_load; netem_off
    ch=0; [ "$lb" != "$la" ] && ch=1
    secs=$((t1 - t0))
    local blocks=$(( ${h1:-0} - ${h0:-0} ))
    local bps=$(awk -v b="$blocks" -v s="$secs" 'BEGIN{printf "%.3f", (s>0)?b/s:0}')
    echo "$arm,$rep,${tgt:-none},$lb,$la,$ch,${h0:-NA},${h1:-NA},$blocks,$secs,$bps" >> "$OUT/results.csv"
    printf "  %-10s rep%d  target=%-24s leader %s->%s%s  blocks=%s in %ss  = %s blk/s\n" \
      "$arm" "$rep" "${tgt:-none}" "$lb" "$la" "$([ $ch = 1 ] && echo ' CHANGED')" \
      "$blocks" "$secs" "$bps" | tee -a "$OUT/summary.txt"
    sleep 20
  done
}

# Arm N first so the ceiling is measured on a clean cluster.
run_arm "N_none" ""

# Follower: pick a node that is NOT the current leader.
L=$(leader_id); [ "$L" = 0 ] && L=2
FOLL=$(( L % N + 1 ))
run_arm "F_follower" "$(cont $FOLL)"

# Leader: re-read it, since the follower arm may have shifted leadership.
L=$(leader_id); [ "$L" = 0 ] && L=2
run_arm "L_leader" "$(cont $L)"

echo "R25_DONE  out=$OUT"; cat "$OUT/results.csv"
