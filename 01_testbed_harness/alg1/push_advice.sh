#!/usr/bin/env bash
# WSL-side pusher: read the predictor's bt.json (blacklist) and inject it as
# orderer advice (/tmp/bora-advice.json) on every orderer, keeping the v3
# sidecars alive (process-checked). The v3 sidecar serves a fresh monotonic seq
# per read, so only the blacklist CONTENT needs pushing here.
set -u
source /mnt/d/fabric-d2/alg1/sidecar_lib.sh
BT=/mnt/d/fabric-d2/results/bt.json
RUN=/tmp/push.on; touch "$RUN"
bl="[]"          # last good blacklist; kept across a failed parse (see below)
echo "[pusher] start"
while [ -f "$RUN" ]; do
  ensure_all_sidecars
  # The daemon serialises with json.dump, whose default separators emit
  # '"blacklist": [3, 10]' -- with spaces.  The previous pattern demanded
  # '"blacklist":[' with no space, so it never matched and this loop pushed an
  # empty blacklist forever: the predictor arm would have looked like a total
  # non-effect, with no error raised anywhere.  Tolerate the spaces, then strip
  # them so the sidecar still receives compact JSON.
  if [ -f "$BT" ]; then
    parsed=$(grep -oE '"blacklist" *: *\[[0-9, ]*\]' "$BT" | grep -oE '\[[0-9, ]*\]' | tr -d ' ')
    # A failed parse means "no reading this instant", not "the blacklist is empty".
    # Falling back to [] would un-blacklist the target for that cycle, which is the
    # one thing this loop must never do by accident; keep the last good value.
    if [ -n "$parsed" ]; then bl="$parsed"; fi
  fi
  for o in "${ALL_ORD[@]}"; do
    docker exec "$o" sh -c "printf '%s' '{\"blacklist\":$bl,\"seq\":1,\"fail_open\":false}' > /tmp/bora-advice.json" 2>/dev/null
  done
  sleep 0.3
done
echo "[pusher] stop"
