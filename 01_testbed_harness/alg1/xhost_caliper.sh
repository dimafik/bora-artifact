#!/usr/bin/env bash
# Run caliper on the dedicated client host against the cross-host cluster.
#
# The load generator sits on its own instance so it does not share CPU with any
# orderer or peer. On the laptop rig the four caliper workers ran beside seven
# orderers and two peers on one kernel, and the per-election throughput varied by
# 26-50%; that contention is the first thing this rig removes.
#
# TLS certs carry FQDN SANs and no IP SANs, so every address must be a name and
# the names are mapped to private IPs with --add-host. Endorsement is
# OR('Org1MSP.member','Org2MSP.member'), so one organisation suffices and the
# connection profile sets discover:false -- no anchor peers required.
#
# Usage: xhost_caliper.sh <tps> <seconds> <label> [workers]
set -u
TPS="${1:?tps}"; DUR="${2:?seconds}"; LABEL="${3:?label}"; W="${4:-4}"
KEY=/tmp/bk.pem; chmod 600 "$KEY" 2>/dev/null
SSH="ssh -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=25 -o BatchMode=yes"
H6=54.180.24.44

ADDH="--add-host orderer.example.com:172.31.39.233 --add-host orderer2.example.com:172.31.44.2 \
--add-host orderer3.example.com:172.31.37.115 --add-host orderer4.example.com:172.31.46.160 \
--add-host orderer5.example.com:172.31.39.145 \
--add-host peer0.org1.example.com:172.31.39.233 --add-host peer0.org2.example.com:172.31.44.2"

$SSH ubuntu@$H6 "cat > /home/ubuntu/caliper-workspace/benchmarks/_xb.yaml" <<YML
test:
  name: xb-$LABEL
  workers: {number: $W}
  rounds:
    - label: $LABEL
      txDuration: $DUR
      rateControl: {type: fixed-rate, opts: {tps: $TPS}}
      workload: {module: workload/createAsset.js}
YML

$SSH ubuntu@$H6 "sudo docker rm -f caliper-xb >/dev/null 2>&1
sudo docker run --rm --name caliper-xb $ADDH \
  -v /home/ubuntu/caliper-workspace:/hyperledger/caliper/workspace \
  -v /home/ubuntu/organizations:/cryptoMount \
  -e CALIPER_BIND_SUT=fabric:fabric-gateway \
  -e CALIPER_BENCHCONFIG=benchmarks/_xb.yaml \
  -e CALIPER_NETWORKCONFIG=networks/fabric-xhost.yaml \
  -e CALIPER_FLOW_ONLY_TEST=true \
  hyperledger/caliper:0.6.0 launch manager > /tmp/caliper_$LABEL.log 2>&1
echo \"exit=\$?\"
grep -aE '\| $LABEL' /tmp/caliper_$LABEL.log | head -2
echo \"errors: \$(grep -ac 'error \[caliper\]' /tmp/caliper_$LABEL.log)\""
