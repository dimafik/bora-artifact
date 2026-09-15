#!/usr/bin/env bash
# Does the rig hold its baseline for as long as a campaign runs?
#
# WHY THIS EXISTS.  The first cross-host campaign reported a clean baseline of
# 290.2 tx/s four times in a row and was declared quiet at 0.03%. Hours later the
# same measurement returned 145 tx/s. The cause was the workload: createAsset.js
# mints a new key per transaction, so the world state grew without limit until
# the peer host's disk hit 79% and endorsement slowed. The drift was invisible
# until it had already spoiled a campaign.
#
# This runs the SAME measurement the campaign will run, back to back, for an hour,
# and prints every result. A rig that is going to sag does it here, before twelve
# hours of measurement are committed to it, not after.
#
# Usage: xhost_calibrate.sh [minutes] [tps] [poolSize]
set -u
MIN="${1:-60}"; TPS="${2:-300}"; POOL="${3:-500}"; W=8; DUR=60
KEY=/tmp/bk.pem; chmod 600 "$KEY" 2>/dev/null
SSH="ssh -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=30 -o BatchMode=yes"
PUB=(x 3.34.1.207 13.124.149.80 13.209.43.120 15.164.234.3 54.180.32.6)
H1=${PUB[1]}; H6=43.201.115.162
D=/mnt/d/fabric-d2
OUT=$D/results/xhost_cal_$(date +%Y%m%d-%H%M%S); mkdir -p "$OUT"
say(){ echo "[$(date +%H:%M:%S)] $*" | tee -a "$OUT/summary.txt"; }
PE1="-e CORE_PEER_ADDRESS=peer0.org1.example.com:7051 -e CORE_PEER_MSPCONFIGPATH=/etc/hyperledger/fabric/adminmsp"
ADDH="--add-host orderer.example.com:172.31.39.233 --add-host orderer2.example.com:172.31.44.2 \
--add-host orderer3.example.com:172.31.37.115 --add-host orderer4.example.com:172.31.46.160 \
--add-host orderer5.example.com:172.31.39.145 \
--add-host peer0.org1.example.com:172.31.39.233 --add-host peer0.org2.example.com:172.31.44.2"

height(){ $SSH ubuntu@$H1 "sudo docker exec $PE1 peer0 peer channel getinfo -c mychannel 2>/dev/null | grep -ao '\"height\":[0-9]*' | grep -ao '[0-9]*'"; }
disk(){ $SSH ubuntu@$1 'df -h / | tail -1 | awk "{print \$5}"'; }

$SSH ubuntu@$H6 "cat > /home/ubuntu/caliper-workspace/benchmarks/_cal.yaml" <<YML
test:
  name: cal
  workers: {number: $W}
  rounds:
    - label: rep
      txDuration: $DUR
      rateControl: {type: fixed-rate, opts: {tps: $TPS}}
      workload:
        module: workload/updateAsset.js
        arguments: {poolSize: $POOL}
YML

say "calibration: ${MIN}min at ${TPS}tx/s, pool=$POOL, ${DUR}s per measurement"
say "output: $OUT"
echo "rep,epoch,success,fail,throughput,latency,height,disk_h1" > "$OUT/results.csv"

END=$(( $(date +%s) + MIN * 60 ))
r=0
while [ "$(date +%s)" -lt "$END" ]; do
  r=$((r+1))
  $SSH ubuntu@$H6 "sudo docker rm -f cal-$r >/dev/null 2>&1
    sudo docker run --rm --name cal-$r $ADDH \
      -v /home/ubuntu/caliper-workspace:/hyperledger/caliper/workspace \
      -v /home/ubuntu/organizations:/cryptoMount \
      -e CALIPER_BIND_SUT=fabric:fabric-gateway \
      -e CALIPER_BENCHCONFIG=benchmarks/_cal.yaml \
      -e CALIPER_NETWORKCONFIG=networks/fabric-xhost-ord1.yaml \
      -e CALIPER_FLOW_ONLY_TEST=true \
      hyperledger/caliper:0.6.0 launch manager > /tmp/cal_$r.log 2>&1
    grep -aE '^\| rep' /tmp/cal_$r.log | head -1" > "$OUT/line_$r.txt" 2>&1
  L=$(cat "$OUT/line_$r.txt")
  S=$(echo "$L" | awk '{print $4}'); F=$(echo "$L" | awk '{print $6}')
  T=$(echo "$L" | awk '{print $16}'); LA=$(echo "$L" | awk '{print $10}')
  H=$(height); DK=$(disk "$H1")
  say "  rep $r: succ=${S:-NA} fail=${F:-NA} tput=${T:-NA} lat=${LA:-NA} height=${H:-NA} disk=${DK:-NA}"
  echo "$r,$(date +%s),${S:-NA},${F:-NA},${T:-NA},${LA:-NA},${H:-NA},${DK:-NA}" >> "$OUT/results.csv"
done

say "===== done: $r measurements ====="
python3 - "$OUT/results.csv" <<'PY'
import csv, sys, statistics as st
rows=[r for r in csv.DictReader(open(sys.argv[1])) if r['throughput'] not in ('NA','')]
t=[float(r['throughput']) for r in rows]
if len(t) >= 2:
    drift = 100.0*(t[-1]-t[0])/t[0]
    print("  throughput first=%.1f last=%.1f min=%.1f max=%.1f" % (t[0], t[-1], min(t), max(t)))
    print("  spread = %.2f%%   first->last drift = %+.2f%%" % (100.0*(max(t)-min(t))/st.mean(t), drift))
    print("  VERDICT: %s" % ("HOLDS (drift within 2%)" if abs(drift) <= 2.0 else "SAGS -- do not start the campaign"))
    f=[int(r['fail']) for r in rows if r['fail'] not in ('NA','')]
    print("  failures total = %d" % sum(f))
PY
