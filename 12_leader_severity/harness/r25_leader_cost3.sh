#!/usr/bin/env bash
# R2-5, second attempt: what does a degraded LEADER cost?
#
# The first attempt (leader_scenario.sh) gave up after 14 tries to put orderer3
# in the leader role and measured a healthy leader by mistake, so its
# "attack_leader" report is really a follower-delay run. Two changes:
#
#   1. UP TO 40 PINNING ATTEMPTS. Each restart of the incumbent gives orderer3
#      roughly a 1-in-4 shot, so 14 tries fail outright 1.8% of the time -- and
#      leadership is not uniform across nodes (healthy nodes vary by 3x in this
#      testbed), so the real per-try odds are worse. 40 tries drives the
#      miss probability to about 1e-3 even at 1-in-6.
#   2. 200 ms, NOT 2000 ms. At 2 s the leader's heartbeats approach the ~5 s
#      election timeout and the degraded leader is deposed within seconds --
#      which destroys the very condition being measured. 200 ms matches the
#      attack used everywhere else in the paper and leaves leadership stable.
#
# The delay is verified OFF during pinning: a target under delay is LESS likely
# to win (measured at 0.42-1.00x chance), so pinning under attack fights itself.
#
# Arms, all with orderer3 delayed except the clean baseline:
#   C_clean     no delay, whoever leads
#   F_follower  orderer3 delayed, a HEALTHY node leads
#   L_leader    orderer3 delayed, ORDERER3 leads      <- the missing measurement
#
# Usage: r25_leader_cost2.sh [delay_ms] [max_pin_tries]
set -u

DLY="${1:-200}"; MAXPIN="${2:-40}"
N=7
D=/mnt/d/fabric-d2
R=$D/results
WS=$D/caliper-workspace
CRYPTO=$D/fabric-samples/test-network/organizations
export PATH=/tmp/bin:$D/fabric-samples/bin-linux/bin:/usr/local/bin:/usr/bin:/bin

ORD=(orderer.example.com orderer2.example.com orderer3.example.com \
     orderer4.example.com orderer5.example.com orderer6.example.com \
     orderer7.example.com)
name_for_id(){ case $1 in 1) echo orderer.example.com;; *) echo "orderer$1.example.com";; esac; }

OUT="$R/r25c_$(date +%Y%m%d-%H%M%S)"; mkdir -p "$OUT"
say(){ echo "$@" | tee -a "$OUT/summary.txt"; }
say "R2-5 leader cost (3rd campaign, N=7, bracketed): delay=${DLY}ms max_pin=$MAXPIN"

# The log-scraping form of this function silently returns EMPTY on a cluster that
# has not held an election recently: "Raft leader changed" scrolls out of even a
# 20000-line tail, and the caller then falls back to orderer1 and restarts the
# wrong node for all MAXPIN attempts. Read the leader from the operations
# endpoint instead, which is authoritative and always current.
# Operations ports are irregular (9xxx belongs to peer0.org2), so map explicitly.
ops_port(){ case "$1" in
  1) echo 7055;; 2) echo 8055;; 3) echo 10055;; 4) echo 11055;;
  5) echo 12055;; 6) echo 13055;; 7) echo 14055;; *) echo "";; esac; }
leader_id(){
  local id p v
  for id in 1 2 3 4 5 6 7; do
    p=$(ops_port "$id"); [ -z "$p" ] && continue
    v=$(curl -s --max-time 3 "http://localhost:${p}/metrics" 2>/dev/null \
        | awk '/^consensus_etcdraft_is_leader\{/{print $2; exit}')
    [ "${v%%.*}" = "1" ] && { echo "$id"; return 0; }
  done
  return 1
}
height(){ docker exec peer0.org1.example.com peer channel getinfo -c mychannel 2>/dev/null \
  | grep -ao '"height":[0-9]*' | grep -ao '[0-9]*'; }

# pumba removes its netem rule on graceful shutdown only. `docker rm -f` kills it
# outright, and the rule survives: after one such teardown orderer3 still showed
# 408 ms with the attack nominally off. Stop it politely, then verify.
stop_attack(){
  docker stop -t 15 pumba-r25 >/dev/null 2>&1 || true
  docker rm -f pumba-r25 >/dev/null 2>&1 || true
  sleep 4
}
start_attack(){ stop_attack
  docker run -d --name pumba-r25 -v /var/run/docker.sock:/var/run/docker.sock \
    gaiaadm/pumba:latest --log-level warning netem --tc-image gaiadocker/iproute2 \
    --duration 40m delay --time "$DLY" orderer3.example.com >/dev/null 2>&1; sleep 6; }

# A stale netem rule left by a killed pumba would silently bias pinning, so the
# absence of delay is verified rather than assumed.
verify_clean(){
  local rtt
  rtt=$(docker run --rm --network fabric_test python:3.11-slim python -c "
import socket,time
t=time.perf_counter()
try:
    s=socket.create_connection(('orderer3.example.com',10050),timeout=3); s.close()
    print('%.1f'%((time.perf_counter()-t)*1000))
except Exception: print('9999')
" 2>/dev/null)
  say "  orderer3 RTT with attack off: ${rtt} ms"
  awk -v r="${rtt:-9999}" 'BEGIN{exit !(r<50)}' || { say "  *** delay still present, aborting"; return 1; }
}

pin_leader_3(){
  say "[pin] target orderer3, up to $MAXPIN attempts (attack off)"
  local i L LC
  for i in $(seq 1 "$MAXPIN"); do
    L=$(leader_id)
    [ "${L:-0}" = "3" ] && { say "  attempt $i: orderer3 IS LEADER"; return 0; }
    LC=$(name_for_id "${L:-1}"); [ -z "$LC" ] && LC=orderer.example.com
    docker restart "$LC" >/dev/null 2>&1
    sleep 14
    [ $((i % 5)) = 0 ] && say "  ...$i tries, current leader=$(leader_id)"
  done
  say "  *** could not pin orderer3 in $MAXPIN attempts"; return 1
}

measure(){                            # $1=label
  local lab="$1" hb ha tb ta lb la
  lb=$(leader_id); hb=$(height); tb=$(date +%s)
  docker rm -f caliper-r25 >/dev/null 2>&1 || true
  docker run --rm --name caliper-r25 --network fabric_test \
    -v "$WS:/hyperledger/caliper/workspace" -v "$CRYPTO:/cryptoMount" \
    --add-host=host.docker.internal:host-gateway \
    -e CALIPER_BIND_SUT=fabric:fabric-gateway \
    -e CALIPER_BENCHCONFIG=benchmarks/belowceiling-sweep.yaml \
    -e CALIPER_NETWORKCONFIG=networks/fabric-5node.yaml \
    -e CALIPER_FLOW_ONLY_TEST=true \
    -e CALIPER_REPORT_PATH=/hyperledger/caliper/workspace/report-r25b-$lab.html \
    hyperledger/caliper:0.6.0 launch manager > "$OUT/caliper_$lab.log" 2>&1
  ha=$(height); ta=$(date +%s); la=$(leader_id)
  cp "$WS/report-r25b-$lab.html" "$OUT/" 2>/dev/null || true
  local delta=$(( ${ha:-0} - ${hb:-0} ))
  # A run that commits nothing is not a slow run, it is a broken one. The first
  # attempt burned 209 s per arm reporting send rate as throughput because the
  # chaincode was absent and every transaction failed; refuse to continue.
  if [ "$delta" -le 0 ]; then
    say ">>> $lab: ledger delta=0 -- NOTHING COMMITTED, measurement invalid"
    say "    (check that chaincode 'basic' is deployed and the peers are healthy)"
    exit 1
  fi
  say ">>> $lab: leader $lb -> $la  ledger delta=$delta in $((ta-tb))s"
  grep -aE "\| rate-[0-9]+" "$OUT/caliper_$lab.log" 2>/dev/null | sed 's/^/    /' | tee -a "$OUT/summary.txt"
  echo "$lab,$lb,$la,${hb:-NA},${ha:-NA},$((ta-tb))" >> "$OUT/arms.csv"
}

trap 'stop_attack; docker rm -f caliper-r25 >/dev/null 2>&1' EXIT INT TERM

# SKIP_SETUP=1 reuses a cluster that is already up with peers joined and the
# chaincode committed. Bring-up plus deploy costs ~13 minutes, and repeating it
# after a mid-run abort wastes that time re-creating a state that already exists.
if [ "${SKIP_SETUP:-0}" = "1" ]; then
  say "===== SKIP_SETUP=1: reusing existing cluster ====="
else
say "===== bring-up N=$N ====="
bash "$D/alg1/nsweep_bringup.sh" "$N" >>"$OUT/timeline.txt" 2>&1 || { say "bring-up failed"; exit 1; }
for o in "${ORD[@]}"; do docker exec "$o" sh -c \
  "printf '%s' '{\"blacklist\":[],\"seq\":1,\"fail_open\":false}' > /tmp/bora-advice.json" 2>/dev/null; done
sleep 10

# nsweep_bringup.sh is an ELECTION harness: it joins the ORDERERS to the channel
# and stops there, because leadership measurements never needed a peer. A
# throughput measurement does. Without the peers on the channel, chaincode
# approval fails with "channel 'mychannel' not found" and every transaction
# fails, which is how the previous attempt reported send rate as throughput.
say "===== join peers to mychannel ====="
TN=$D/fabric-samples/test-network
# JoinChain is an Admins-policy operation. The MSP baked into a peer container is
# the PEER identity, which lacks OU=ADMIN, so joining with it fails with
# "The identity does not contain OU [ADMIN]". test-network normally solves this
# with a cli container carrying Admin@orgN credentials; no cli container exists
# here, so the admin MSP is copied into the peer and pointed at explicitly.
for spec in \
 "peer0.org1.example.com Org1MSP org1.example.com peer0.org1.example.com:7051" \
 "peer0.org2.example.com Org2MSP org2.example.com peer0.org2.example.com:9051"; do
  set -- $spec
  PC="$1"; MSPID="$2"; ORGDOM="$3"; ADDR="$4"
  docker cp "$TN/channel-artifacts/mychannel.block" "$PC:/tmp/mychannel.block" >/dev/null 2>&1
  docker cp "$TN/organizations/peerOrganizations/$ORGDOM/users/Admin@$ORGDOM/msp" \
            "$PC:/tmp/adminmsp" >/dev/null 2>&1
  docker exec -e CORE_PEER_LOCALMSPID="$MSPID" \
              -e CORE_PEER_MSPCONFIGPATH=/tmp/adminmsp \
              -e CORE_PEER_TLS_ROOTCERT_FILE=/etc/hyperledger/fabric/tls/ca.crt \
              -e CORE_PEER_ADDRESS="$ADDR" \
    "$PC" peer channel join -b /tmp/mychannel.block >>"$OUT/timeline.txt" 2>&1
done
sleep 8
for p in peer0.org1.example.com peer0.org2.example.com; do
  if docker exec "$p" peer channel list 2>/dev/null | grep -q mychannel; then
    say "  $p joined"
  else
    say "  *** $p did NOT join mychannel"; exit 1
  fi
done

# The election harness deploys no chaincode; caliper's workload calls contract
# 'basic'. Go lives outside PATH in this WSL image, and packaging needs it.
export PATH="$HOME/go-install/bin:$PATH"
command -v go >/dev/null || { say "*** go not found; chaincode cannot be packaged"; exit 1; }
say "  go: $(go version)"
say "===== deploy chaincode 'basic' ====="
# querycommitted is also an admin-gated call. Checking it with the peer's own
# identity reports failure even when the deploy succeeded -- which is exactly
# what aborted the previous run after network.sh had in fact committed the
# definition. Use the admin MSP copied in during the join step.
cc_committed(){
  docker exec -e CORE_PEER_LOCALMSPID=Org1MSP -e CORE_PEER_MSPCONFIGPATH=/tmp/adminmsp \
    peer0.org1.example.com peer lifecycle chaincode querycommitted \
    --channelID mychannel --name basic 2>/dev/null | grep -q "Version: 1.0"
}
if cc_committed; then
  say "  already committed"
else
  ( cd "$D/fabric-samples/test-network" && \
    ./network.sh deployCC -c mychannel -ccn basic \
      -ccp ../asset-transfer-basic/chaincode-go -ccl go ) \
    >>"$OUT/timeline.txt" 2>&1
  cc_committed || { say "  *** chaincode deploy failed, see timeline.txt"; exit 1; }
  say "  deployed"
fi
fi   # end SKIP_SETUP

# Whatever path got us here, the measurement is meaningless without these.
cc_ok(){ docker exec -e CORE_PEER_LOCALMSPID=Org1MSP -e CORE_PEER_MSPCONFIGPATH=/tmp/adminmsp \
  peer0.org1.example.com peer lifecycle chaincode querycommitted \
  --channelID mychannel --name basic 2>/dev/null | grep -q "Version: 1.0"; }
cc_ok || { say "*** chaincode 'basic' is not committed - cannot measure"; exit 1; }
say "  precondition OK: chaincode committed, $(docker ps -q -f name=orderer | wc -l) orderers up"
echo "arm,leader_before,leader_after,h0,h1,secs" > "$OUT/arms.csv"

say "===== C_clean (no delay) ====="
stop_attack; verify_clean || exit 1
measure "C_clean"

say "===== F_follower (orderer3 delayed, healthy leader) ====="
L=$(leader_id)
if [ "${L:-0}" = "3" ]; then docker restart orderer3.example.com >/dev/null 2>&1; sleep 16; fi
say "  leader is $(leader_id) (must not be 3)"
start_attack
measure "F_follower"
stop_attack; sleep 8

say "===== L_leader (orderer3 delayed AND leading) ====="
verify_clean || exit 1
if pin_leader_3; then
  start_attack
  say "  leader right after attack starts: $(leader_id)"
  measure "L_leader"
else
  say "  L_leader SKIPPED - pinning failed"
fi
stop_attack

# Bracket. The three arms always run in the same order, so any drift over the
# ~20 min of a run would be charged entirely to L_leader. Re-measuring the clean
# condition at the END bounds that drift directly: C_clean_post vs C_clean is
# the run's own noise floor.
# It also serves as a second control. By this point orderer3 is the leader and
# the delay is off, so C_clean_post answers "is orderer3 simply a slow node?"
# separately from "does the injected delay hurt when it leads".
say "===== C_clean_post (bracket: no delay, end of run) ====="
stop_attack; sleep 8
if verify_clean; then
  say "  leader for bracket: $(leader_id)"
  measure "C_clean_post"
else
  say "  *** bracket skipped: delay residue (main arms above are unaffected)"
fi

say "R25C_DONE  out=$OUT"
cat "$OUT/arms.csv"
