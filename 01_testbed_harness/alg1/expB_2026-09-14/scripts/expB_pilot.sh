#!/usr/bin/env bash
# Experiment B, pilot -- does the guard buy measurable THROUGHPUT over a horizon
# that contains forced elections?
#
# WHY THIS EXISTS.  Section V-D answers R2-5 in three steps: throughput
# neutrality (argued), the cost of a degraded LEADER (measured, 65% at N=7,
# +200 ms), and how often the unguarded arm actually puts the degraded node
# there (measured, 21 of 240, +200 ms).  The second and third come from two
# different campaigns; the paper reports them side by side rather than as a product.  x1_closedloop.sh records
# elections and never touches a client -- it does not even join the peers to the
# channel -- so the throughput DURING those 21 terms was never observed.
#
# WHAT IT MEASURES.  Committed ledger growth under one continuous Caliper load,
# per arm, with the same forced-election pattern running underneath:
#   Arm A  vanilla  B_t = []      the degraded node may take leadership
#   Arm B  guarded  B_t = [3]     it may not
# If the synthesis is right the gap is about the acquisition rate times the
# leader-side cost: 0.0875 x 0.65 ~ 5-6%.
#
# WHY OPERATOR-SUPPLIED AND NOT THE PREDICTOR.  The question is what the GUARD is
# worth, not what the detector is worth.  Section V-B already shows the
# operator-supplied and detector-produced arms are indistinguishable in exclusion
# power, so the cheaper arm is the right ablation here.
#
# PILOT, NOT THE STUDY.  One seed.  At N=7 the chance share is 16.7%, so ten
# elections seat the degraded node once or twice in Arm A; the point is to see
# the magnitude against the noise, not to publish a number.  If the effect is
# invisible here it will not survive four seeds either, and the existing
# argument -- frequency and cost measured separately -- stays as it is.
#
# The bring-up, peer join, chaincode deploy, leader read and pumba teardown are
# taken from r25_leader_cost3.sh, the campaign that measured the 65%, so the two
# measurements sit on the same network rather than merely near each other.
#
# Usage: [SKIP_SETUP=1] expB_pilot.sh [N] [elections] [tps] [delay_ms]
set -u

N="${1:-7}"; NE="${2:-10}"; TPS="${3:-200}"; DLY="${4:-200}"
TARGET=3

D=/mnt/d/fabric-d2
R=$D/results
WS=$D/caliper-workspace
TN=$D/fabric-samples/test-network
CRYPTO=$TN/organizations
export PATH=/tmp/bin:$D/fabric-samples/bin-linux/bin:/usr/local/bin:/usr/bin:/bin
export N_ORD="$N"
source $D/alg1/sidecar_lib.sh

OUT=$R/expB_pilot_$(date +%Y%m%d-%H%M%S); mkdir -p "$OUT"
say(){ echo "[$(date +%H:%M:%S)] $*" | tee -a "$OUT/summary.txt"; }

host(){ [ "$1" = 1 ] && echo orderer || echo "orderer$1"; }
cont(){ echo "$(host $1).example.com"; }
ORD=(); for i in $(seq 1 "$N"); do ORD+=("$(cont $i)"); done
TCONT=$(cont $TARGET)

say "Experiment B pilot: N=$N elections=$NE load=${TPS}tx/s delay=+${DLY}ms target=orderer$TARGET"
say "output: $OUT"

# ------------------------------------------------------------------ primitives
# Leadership from the operations endpoint, not the log: "Raft leader changed"
# scrolls out of even a long tail on a cluster that has been quiet, and the
# log-scraping form then silently returns the wrong node.
ops_port(){ case "$1" in 1) echo 7055;; 2) echo 8055;; *) echo $(( 10055 + 1000 * ($1 - 3) ));; esac; }
leader_id(){
  local id p v
  for id in $(seq 1 "$N"); do
    p=$(ops_port "$id"); [ -z "$p" ] && continue
    v=$(curl -s --max-time 3 "http://localhost:${p}/metrics" 2>/dev/null \
        | awk '/^consensus_etcdraft_is_leader\{/{print $2; exit}')
    [ "${v%%.*}" = "1" ] && { echo "$id"; return 0; }
  done
  echo 0; return 1
}
height(){ docker exec peer0.org1.example.com peer channel getinfo -c mychannel 2>/dev/null \
  | grep -ao '"height":[0-9]*' | grep -ao '[0-9]*'; }

set_all(){ local s="$1"; for o in "${ORD[@]}"; do
  docker exec "$o" sh -c "printf '%s' '{\"blacklist\":$s,\"seq\":1,\"fail_open\":false}' > /tmp/bora-advice.json" 2>/dev/null
done; }

ATT_MIN=$(( (2 * NE * 20) / 60 + 30 ))
start_attack(){
  docker rm -f pumba-expb >/dev/null 2>&1
  docker run -d --name pumba-expb -v /var/run/docker.sock:/var/run/docker.sock \
    gaiaadm/pumba:latest --log-level warning netem --tc-image gaiadocker/iproute2 \
    --duration "${ATT_MIN}m" delay --time "$DLY" "$TCONT" >/dev/null 2>&1
  sleep 6
}
check_attack(){ [ -n "$(docker ps -q -f name=pumba-expb 2>/dev/null)" ] && return 0
                say "  WARN pumba died at $1 -- restarting"; start_attack; }
# pumba removes its netem rule on graceful shutdown only; `rm -f` leaves it behind.
stop_attack(){ docker stop -t 15 pumba-expb >/dev/null 2>&1 || true
               docker rm -f pumba-expb >/dev/null 2>&1 || true; sleep 4; }

trap 'stop_attack; docker rm -f caliper-expb >/dev/null 2>&1; rm -f /tmp/expb_heal' EXIT INT TERM

gen_bench(){ cat > "$WS/benchmarks/_expb.yaml" <<YML
test:
  name: expb-$1
  workers: {number: 4}
  rounds:
    - label: expb-$1
      txDuration: $2
      rateControl: {type: fixed-rate, opts: {tps: $1}}
      workload: {module: workload/createAsset.js}
YML
}
start_load(){ gen_bench "$1" "$2"
  docker rm -f caliper-expb >/dev/null 2>&1 || true
  docker run --rm --name caliper-expb --network fabric_test \
    -v "$WS:/hyperledger/caliper/workspace" -v "$CRYPTO:/cryptoMount" \
    --add-host=host.docker.internal:host-gateway \
    -e CALIPER_BIND_SUT=fabric:fabric-gateway \
    -e CALIPER_BENCHCONFIG=benchmarks/_expb.yaml \
    -e CALIPER_NETWORKCONFIG=networks/fabric-5node.yaml \
    -e CALIPER_FLOW_ONLY_TEST=true \
    -e CALIPER_REPORT_PATH=/hyperledger/caliper/workspace/report-expb-$3.html \
    hyperledger/caliper:0.6.0 launch manager > "$OUT/caliper_$3.log" 2>&1 &
  CALPID=$!
}
stop_load(){ docker rm -f caliper-expb >/dev/null 2>&1 || true
             [ "${CALPID:-0}" != "0" ] && kill "$CALPID" 2>/dev/null; CALPID=0; }

# -------------------------------------------------------------------- setup
if [ "${SKIP_SETUP:-0}" = "1" ]; then
  say "===== SKIP_SETUP=1: reusing the cluster that is already up ====="
else
say "===== bring-up N=$N ====="
bash "$D/alg1/nsweep_bringup.sh" "$N" >>"$OUT/timeline.txt" 2>&1 || { say "bring-up failed"; exit 1; }
set_all "[]"; sleep 10

# nsweep_bringup.sh is an ELECTION harness: it joins the ORDERERS and stops,
# because leadership measurements never needed a peer. A throughput measurement
# does. JoinChain is an Admins-policy call and the MSP baked into the peer is the
# PEER identity, so the admin MSP is copied in and pointed at explicitly.
say "===== join peers to mychannel ====="
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
  docker exec "$p" peer channel list 2>/dev/null | grep -q mychannel \
    && say "  $p joined" || { say "  *** $p did NOT join mychannel"; exit 1; }
done

# The caliper network config uses `discover: true`, and service discovery can
# only find the other organisation's endorsers if that org has an ANCHOR PEER in
# the channel config. nsweep_bringup.sh never sets one, because a leadership
# experiment endorses nothing. Without anchors caliper fails every transaction
# with "no combination of peers can be derived which satisfy the endorsement
# policy" while the ledger sits still -- which is exactly how the first pilot
# reported two arms of zero committed blocks.
say "===== set anchor peers ====="
bash "$D/alg1/_set_anchors.sh" >>"$OUT/timeline.txt" 2>&1
grep -q "ANCHOR_OK org2" "$OUT/timeline.txt" || { say "*** anchor peers not set"; exit 1; }
say "  anchors set for org1 and org2"

export PATH="$HOME/go-install/bin:$PATH"
command -v go >/dev/null || { say "*** go not found; chaincode cannot be packaged"; exit 1; }
say "===== deploy chaincode 'basic' ====="
cc_committed(){ docker exec -e CORE_PEER_LOCALMSPID=Org1MSP -e CORE_PEER_MSPCONFIGPATH=/tmp/adminmsp \
  peer0.org1.example.com peer lifecycle chaincode querycommitted \
  --channelID mychannel --name basic 2>/dev/null | grep -q "Version: 1.0"; }
if cc_committed; then say "  already committed"; else
  ( cd "$TN" && ./network.sh deployCC -c mychannel -ccn basic \
      -ccp ../asset-transfer-basic/chaincode-go -ccl go ) >>"$OUT/timeline.txt" 2>&1
  cc_committed || { say "  *** chaincode deploy failed, see timeline.txt"; exit 1; }
  say "  deployed"
fi
fi   # end SKIP_SETUP

cc_ok(){ docker exec -e CORE_PEER_LOCALMSPID=Org1MSP -e CORE_PEER_MSPCONFIGPATH=/tmp/adminmsp \
  peer0.org1.example.com peer lifecycle chaincode querycommitted \
  --channelID mychannel --name basic 2>/dev/null | grep -q "Version: 1.0"; }
cc_ok || { say "*** chaincode 'basic' is not committed - cannot measure"; exit 1; }
H0=$(height); [ -z "$H0" ] && { say "*** cannot read ledger height"; exit 1; }
say "  precondition OK: chaincode committed, height=$H0, $(docker ps -q -f name=orderer | wc -l) orderers up"

ensure_all_sidecars
RUNH=/tmp/expb_heal; touch $RUNH
( while [ -f $RUNH ]; do ensure_all_sidecars; sleep 3; done ) & HP=$!

say "===== injecting +${DLY}ms on $TCONT for ${ATT_MIN}m ====="
start_attack
say "  pumba up: $(docker ps -q -f name=pumba-expb | head -c 12)"

echo "arm,elec,leader_before,leader_after,target_won,height_before,height_after" > "$OUT/elections.csv"
echo "arm,height_start,height_end,blocks,seconds,blocks_per_s,target_terms" > "$OUT/arms.csv"

# ----------------------------------------------------------------------- arms
run_arm(){ # $1 = arm name, $2 = blacklist literal
  local arm="$1" bl="$2" k L NL HB HA won=0 hs he t0 t1 dur
  say "===== arm $arm  (B_t = $bl) ====="
  set_all "$bl"; sleep 2
  dur=$(( 40 + NE * 20 + 30 ))
  start_load "$TPS" "$dur" "$arm"
  say "  caliper up, ${dur}s round; 40s warm-up before the first election"
  sleep 40
  set_all "$bl"                     # re-assert: a sidecar restart clears it

  t0=$(date +%s); hs=$(height)
  say "  arm $arm starts at height ${hs:-NA}"

  for k in $(seq 1 "$NE"); do
    check_attack "arm $arm election $k"
    set_all "$bl"
    HB=$(height); L=$(leader_id); [ "${L:-0}" = 0 ] && L=1
    # Forced election by PAUSE, never restart: a restart kills the sidecar and
    # the container's netem, turning a guarded arm into an unguarded one.
    docker pause "$(cont $L)" >/dev/null 2>&1
    sleep 9
    NL=$(leader_id)
    docker unpause "$(cont $L)" >/dev/null 2>&1
    sleep 6
    HA=$(height)
    [ "$NL" = "$TARGET" ] && won=$((won+1))
    echo "$arm,$k,$L,$NL,$([ "$NL" = "$TARGET" ] && echo 1 || echo 0),${HB:-NA},${HA:-NA}" >> "$OUT/elections.csv"
    say "  e$k: leader $L -> $NL$([ "$NL" = "$TARGET" ] && echo '   <-- TARGET LEADS')  h ${HB:-NA}->${HA:-NA}"
  done

  t1=$(date +%s); he=$(height)
  stop_load
  local secs=$((t1 - t0)) blocks=$(( ${he:-0} - ${hs:-0} ))
  # A run that commits nothing is not a slow run, it is a broken one. Continuing
  # would put two zeros in arms.csv and invite reading them as "no difference".
  if [ "$blocks" -le 0 ]; then
    say "  >>> arm $arm committed NOTHING (delta=$blocks) -- measurement invalid, stopping"
    say "      (check anchor peers, chaincode 'basic', and caliper_$arm.log)"
    exit 1
  fi
  say "  >>> arm $arm: height $hs -> $he  (+$blocks blocks in ${secs}s), target led $won/$NE"
  grep -aE "\| rate-[0-9]+" "$OUT/caliper_$arm.log" 2>/dev/null | sed 's/^/      /' | tee -a "$OUT/summary.txt"
  echo "$arm,$hs,$he,$blocks,$secs,$(awk -v b=$blocks -v s=$secs 'BEGIN{printf "%.4f",(s>0)?b/s:0}'),$won" >> "$OUT/arms.csv"
  set_all "[]"; sleep 3
}

run_arm vanilla "[]"
run_arm guarded "[$TARGET]"

rm -f $RUNH; kill $HP 2>/dev/null || true
stop_attack; set_all "[]"
say "===== pilot done ====="
cat "$OUT/arms.csv" | tee -a "$OUT/summary.txt"
say "artifacts: $OUT"
