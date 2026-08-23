#!/usr/bin/env bash
# Distribute per-orderer material to each of the 5 hosts and launch one orderer
# container per host (Fabric image; BORA binary swapped in afterward by xhost_bora.sh).
set -u
KEY=/tmp/bk.pem; chmod 600 "$KEY" 2>/dev/null
OUT=/mnt/d/fabric-d2/results/xhost
SSH="ssh -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=15 -o BatchMode=yes"
SCP="scp -i $KEY -o StrictHostKeyChecking=no -o ConnectTimeout=15 -q"
PUB=(43.201.73.122 54.180.99.165 43.201.25.172 54.180.117.221 15.164.226.99)
PRIV=(172.31.39.233 172.31.44.2 172.31.37.115 172.31.46.160 172.31.39.145)
HOSTN=(orderer orderer2 orderer3 orderer4 orderer5)
ADDH="--add-host orderer.example.com:172.31.39.233 --add-host orderer2.example.com:172.31.44.2 --add-host orderer3.example.com:172.31.37.115 --add-host orderer4.example.com:172.31.46.160 --add-host orderer5.example.com:172.31.39.145"

for i in 0 1 2 3 4; do
  ip=${PUB[$i]}; hn=${HOSTN[$i]}
  echo "=== host $ip = $hn.example.com ==="
  $SSH ubuntu@$ip 'rm -rf ~/ord && mkdir -p ~/ord'
  $SCP -r "$OUT/$hn/msp" ubuntu@$ip:~/ord/msp
  $SCP -r "$OUT/$hn/tls" ubuntu@$ip:~/ord/tls
  $SCP "$OUT/mychannel.block" "$OUT/orderer-ca.pem" "$OUT/orderer-bora-v4.bin" "$OUT/bora-sidecar-v3.bin" ubuntu@$ip:~/ord/
  $SSH ubuntu@$ip "sudo docker rm -f orderer >/dev/null 2>&1; sudo docker run -d --name orderer --network host $ADDH \
    -e ORDERER_GENERAL_LISTENADDRESS=0.0.0.0 -e ORDERER_GENERAL_LISTENPORT=7050 \
    -e ORDERER_GENERAL_LOCALMSPID=OrdererMSP -e ORDERER_GENERAL_LOCALMSPDIR=/var/hyperledger/orderer/msp \
    -e ORDERER_GENERAL_TLS_ENABLED=true -e ORDERER_GENERAL_TLS_PRIVATEKEY=/var/hyperledger/orderer/tls/server.key \
    -e ORDERER_GENERAL_TLS_CERTIFICATE=/var/hyperledger/orderer/tls/server.crt -e ORDERER_GENERAL_TLS_ROOTCAS=[/var/hyperledger/orderer/tls/ca.crt] \
    -e ORDERER_GENERAL_CLUSTER_CLIENTCERTIFICATE=/var/hyperledger/orderer/tls/server.crt -e ORDERER_GENERAL_CLUSTER_CLIENTPRIVATEKEY=/var/hyperledger/orderer/tls/server.key \
    -e ORDERER_GENERAL_CLUSTER_ROOTCAS=[/var/hyperledger/orderer/tls/ca.crt] \
    -e ORDERER_GENERAL_BOOTSTRAPMETHOD=none -e ORDERER_CHANNELPARTICIPATION_ENABLED=true \
    -e ORDERER_ADMIN_TLS_ENABLED=true -e ORDERER_ADMIN_LISTENADDRESS=0.0.0.0:7053 \
    -e ORDERER_ADMIN_TLS_CERTIFICATE=/var/hyperledger/orderer/tls/server.crt -e ORDERER_ADMIN_TLS_PRIVATEKEY=/var/hyperledger/orderer/tls/server.key \
    -e ORDERER_ADMIN_TLS_ROOTCAS=[/var/hyperledger/orderer/tls/ca.crt] -e ORDERER_ADMIN_TLS_CLIENTROOTCAS=[/var/hyperledger/orderer/tls/ca.crt] \
    -e ORDERER_OPERATIONS_LISTENADDRESS=127.0.0.1:9443 -e FABRIC_LOGGING_SPEC=INFO \
    -v /home/ubuntu/ord/msp:/var/hyperledger/orderer/msp -v /home/ubuntu/ord/tls:/var/hyperledger/orderer/tls \
    hyperledger/fabric-orderer:latest >/dev/null 2>&1 && echo '  launched' || echo '  LAUNCH_FAIL'"
done
echo "=== wait 12s, check containers ==="
sleep 12
for i in 0 1 2 3 4; do
  st=$($SSH ubuntu@${PUB[$i]} 'sudo docker inspect -f "{{.State.Status}}" orderer 2>/dev/null')
  echo "  ${HOSTN[$i]} ($state): ${st:-NA}"
done
echo "XHOST_DEPLOY_DONE"
