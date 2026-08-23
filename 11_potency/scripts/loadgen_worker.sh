#!/bin/sh
# Runs inside the load container.  Kept as a file rather than passed to
# `docker exec sh -c "..."`: that form has to survive Git Bash path conversion
# and three levels of quoting for the chaincode JSON, and when it broke it broke
# silently -- the workers never started, no error surfaced anywhere, and the run
# reported zero transactions as though the cluster had refused them.
#
# Env: SECS WORKERS CH CC ORDERER_CA O1CA O2CA
set -u

: "${SECS:?}" "${WORKERS:?}" "${CH:?}" "${CC:?}"
: "${PACE:=1.0}"
# Keys must be unique across runs, not just within one.  The first version
# used the container shell PID, which a fresh container reissues almost
# identically every time, so the second run tried to create assets the first
# had already created and CreateAsset rejected them.  That looked exactly
# like the cluster refusing load: 0 successes, no error surfaced.
: "${RUNID:?run identifier, unique per invocation}"

w=1
while [ "$w" -le "$WORKERS" ]; do
  (
    i=0
    ok=0
    end=$(( $(date +%s) + SECS ))
    while [ "$(date +%s)" -lt "$end" ]; do
      i=$((i + 1))
      # Paced, not flat out.  Unthrottled, four workers offered about 42 tx/s and
      # only 2.5% were accepted -- but worse, the offered load would then depend
      # on the condition being measured, since a slower cluster completes fewer
      # attempts per second.  Comparing committed blocks across conditions
      # requires the *offered* rate to be the same in each, so each worker holds
      # a fixed interval and the cluster is never pushed into the regime where it
      # starts refusing.
      sleep "$PACE"
      if peer chaincode invoke \
           -o orderer.example.com:7050 \
           --ordererTLSHostnameOverride orderer.example.com \
           --tls --cafile "$ORDERER_CA" \
           -C "$CH" -n "$CC" \
           --peerAddresses peer0.org1.example.com:7051 --tlsRootCertFiles "$O1CA" \
           --peerAddresses peer0.org2.example.com:9051 --tlsRootCertFiles "$O2CA" \
           -c "{\"function\":\"CreateAsset\",\"Args\":[\"${RUNID}-w${w}-${i}\",\"blue\",\"5\",\"tom\",\"100\"]}" \
           >/dev/null 2>&1
      then
        ok=$((ok + 1))
      fi
    done
    echo "$ok $i" > "/tmp/w${w}.done"
  ) &
  w=$((w + 1))
done

wait
echo done > /tmp/all.done
