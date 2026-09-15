#!/usr/bin/env bash
# Isolate what actually moved the throughput between the pilot's two arms.
#
# The pilot's guarded arm committed 38% fewer transactions than its vanilla arm,
# and the settled-window rate with a HEALTHY leader differed just as much
# (19.6 vs 8.6 blocks/s) even though orderer3 was a follower in both. Election
# recovery was fast in both (0.2 s vs 1.5 s), so the gap is in steady state, not
# in the transitions. Three conditions, no elections, same leader throughout:
#
#   A  no delay,      B_t = []      the rig's baseline
#   B  o3 delayed,    B_t = []      the follower-delay neutrality claim
#   C  o3 delayed,    B_t = [3]     the same, with the guard standing
#
# A vs B tests the claim that a delayed FOLLOWER costs nothing. B vs C tests
# whether the blacklist itself costs anything while it stands. The paper asserts
# both are free; this measures them separately rather than inferring.
set -u
REPS="${1:-3}"; TPS="${2:-300}"; DUR="${3:-60}"; DLY="${4:-200}"
KEY=/tmp/bk.pem; chmod 600 "$KEY" 2>/dev/null
SSH="ssh -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=25 -o BatchMode=yes"
PUB=(x 43.201.32.112 43.200.5.112 52.79.120.204 54.180.116.11 13.125.227.200)
H3=${PUB[3]}; IF3=ens5; N=5; W=8
D=/mnt/d/fabric-d2
H6=54.180.24.44
OUT=$D/results/expB_iso_$(date +%Y%m%d-%H%M%S); mkdir -p "$OUT"
say(){ echo "[$(date +%H:%M:%S)] $*" | tee -a "$OUT/summary.txt"; }
sshi(){ local i=$1; shift; $SSH ubuntu@${PUB[$i]} "$@"; }

leader_id(){
  local i best=-1 bid=0 t
  for i in $(seq 1 $N); do
    t=$(sshi $i "sudo docker logs orderer 2>&1 | grep -ao 'became leader at term [0-9]*' | tail -1 | grep -ao '[0-9]*\$'")
    [ -n "$t" ] && [ "$t" -gt "$best" ] && { best=$t; bid=$i; }
  done
  echo "$bid"
}
set_all(){ local i; for i in $(seq 1 $N); do
  sshi $i "sudo docker exec orderer sh -c \"printf '%s' '{\\\"blacklist\\\":$1,\\\"seq\\\":1,\\\"fail_open\\\":false}' > /tmp/bora-advice.json\"" 2>/dev/null
done; }
delay_on(){ $SSH ubuntu@$H3 "sudo tc qdisc replace dev $IF3 root netem delay ${DLY}ms limit 10000" >/dev/null 2>&1
  local q; q=$($SSH ubuntu@$H3 "tc qdisc show dev $IF3 | grep -o 'netem.*'" 2>/dev/null)
  [ -z "$q" ] && { say "  FATAL netem did not apply"; exit 1; }; }
delay_off(){ $SSH ubuntu@$H3 "sudo tc qdisc del dev $IF3 root" >/dev/null 2>&1; }
trap 'delay_off; $SSH ubuntu@$H6 "sudo docker rm -f caliper-xb" >/dev/null 2>&1' EXIT INT TERM

run(){ # $1 label
  bash $D/alg1/xhost_caliper.sh "$TPS" "$DUR" "$1" "$W" > "$OUT/cal_$1.txt" 2>&1
  local l; l=$(grep -aE "^\| $1" "$OUT/cal_$1.txt" | head -1)
  echo "$l" | awk -v n="$1" '{printf "  %-10s succ=%-7s fail=%-7s tput=%-7s lat=%s\n", n,$4,$6,$16,$10}' | tee -a "$OUT/summary.txt"
  echo "$1,$(echo "$l" | awk '{print $4","$6","$16","$10}')" >> "$OUT/results.csv"
}

echo "cond,success,fail,throughput,latency" > "$OUT/results.csv"
say "isolation: reps=$REPS tps=$TPS dur=${DUR}s delay=+${DLY}ms"
delay_off; set_all "[]"; sleep 3
say "  leader = orderer$(leader_id)  (must not be 3 for any of these to mean what they say)"

for r in $(seq 1 "$REPS"); do
  say "===== rep $r ====="
  delay_off; set_all "[]"; sleep 4;            run "A_clean_r$r"
  delay_on;  set_all "[]"; sleep 4;            run "B_delay_r$r"
  delay_on;  set_all "[3]"; sleep 4;           run "C_delay_bl_r$r"
  delay_off; set_all "[]"
  say "  leader after rep $r = orderer$(leader_id)"
done
say "===== done ====="
cat "$OUT/results.csv" | tee -a "$OUT/summary.txt"
say "artifacts: $OUT"
