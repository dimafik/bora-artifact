#!/bin/sh
# Per-transaction commit latency, recorded one line per invoke.
#
# --waitForEvent is the point of this script.  Without it `peer chaincode invoke`
# returns once the orderer has *accepted* the transaction, which measures
# endorsement and submission and says nothing about how long the ordering
# service took to commit -- exactly the quantity a bursty delay is expected to
# stretch.  With it, the call returns on the commit event from the peer's
# deliver service, so the wall time is end-to-end.
#
# Failures are recorded too, with a negative duration, rather than dropped: a
# condition that commits fewer but faster transactions would otherwise look
# better than one that commits everything.
#
# Env: SECS WORKERS CH CC ORDERER_CA O1CA O2CA PACE RUNID
set -u

: "${SECS:?}" "${WORKERS:?}" "${CH:?}" "${CC:?}" "${RUNID:?}"
: "${PACE:=1.0}"

rm -f /tmp/lat.*.csv /tmp/all.done

w=1
while [ "$w" -le "$WORKERS" ]; do
  (
    i=0
    end=$(( $(date +%s) + SECS ))
    out="/tmp/lat.${w}.csv"
    : > "$out"
    while [ "$(date +%s)" -lt "$end" ]; do
      i=$((i + 1))
      sleep "$PACE"
      t0=$(date +%s%N)
      if peer chaincode invoke \
           -o orderer.example.com:7050 \
           --ordererTLSHostnameOverride orderer.example.com \
           --tls --cafile "$ORDERER_CA" \
           -C "$CH" -n "$CC" \
           --waitForEvent --waitForEventTimeout 60s \
           --peerAddresses peer0.org1.example.com:7051 --tlsRootCertFiles "$O1CA" \
           --peerAddresses peer0.org2.example.com:9051 --tlsRootCertFiles "$O2CA" \
           -c "{\"function\":\"CreateAsset\",\"Args\":[\"${RUNID}-w${w}-${i}\",\"blue\",\"5\",\"tom\",\"100\"]}" \
           >/dev/null 2>&1
      then
        t1=$(date +%s%N)
        echo "$(( (t1 - t0) / 1000000 ))" >> "$out"
      else
        t1=$(date +%s%N)
        echo "-$(( (t1 - t0) / 1000000 ))" >> "$out"
      fi
    done
  ) &
  w=$((w + 1))
done

wait
echo done > /tmp/all.done
