#!/usr/bin/env bash
# Join all 5 cross-host orderers to mychannel by running osnadmin ON each host
# against its local admin endpoint (localhost:7053). The admin port is only open
# inside the SG, so we cannot reach it from outside; running on-host avoids that.
set -u
KEY=/tmp/bk.pem; chmod 600 "$KEY" 2>/dev/null
OSN=/mnt/d/fabric-d2/fabric-samples/bin-linux/bin/osnadmin
SSH="ssh -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=15 -o BatchMode=yes"
SCP="scp -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=15 -q"
PUB=(43.201.73.122 54.180.99.165 43.201.25.172 54.180.117.221 15.164.226.99)
HOSTN=(orderer orderer2 orderer3 orderer4 orderer5)

echo "=== copy osnadmin to each host ==="
for ip in "${PUB[@]}"; do $SCP "$OSN" ubuntu@$ip:~/ord/osnadmin; $SSH ubuntu@$ip 'chmod +x ~/ord/osnadmin'; done

echo "=== channel join on each host (localhost:7053) ==="
for i in 0 1 2 3 4; do
  ip=${PUB[$i]}
  r=$($SSH ubuntu@$ip '~/ord/osnadmin channel join --channelID mychannel --config-block ~/ord/mychannel.block -o localhost:7053 --ca-file ~/ord/orderer-ca.pem --client-cert ~/ord/tls/server.crt --client-key ~/ord/tls/server.key 2>&1 | grep -oE "Status: 201|already exists|Error.*" | head -1')
  echo "  ${HOSTN[$i]}: ${r:-NO-RESPONSE}"
done
sleep 8
echo "=== channel list per host ==="
J=0
for i in 0 1 2 3 4; do
  ip=${PUB[$i]}
  c=$($SSH ubuntu@$ip '~/ord/osnadmin channel list -o localhost:7053 --ca-file ~/ord/orderer-ca.pem --client-cert ~/ord/tls/server.crt --client-key ~/ord/tls/server.key 2>&1 | grep -c mychannel')
  [ "${c:-0}" -ge 1 ] && J=$((J+1))
  echo "  ${HOSTN[$i]}: mychannel=${c:-0}"
done
echo "joined: $J/5"
echo "=== leader (Raft leader changed) from orderer1 host ==="
$SSH ubuntu@${PUB[0]} 'sudo docker logs --tail 200 orderer 2>&1 | grep -aoE "Raft leader changed: [0-9]+ -> [0-9]+" | tail -2'
echo "XHOST_JOIN_DONE"
