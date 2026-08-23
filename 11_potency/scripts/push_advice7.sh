#!/usr/bin/env bash
# Push the detector's blacklist into every orderer's advice file.
#
# Same job as push_advice.sh, with two changes it needs here: seven orderers
# instead of five, and Git Bash paths instead of the WSL /mnt/d ones.
#
# The parse tolerates the spaces json.dump emits ('"blacklist": [3]').  An
# earlier version demanded no space, never matched, and pushed an empty
# blacklist forever -- the predictor arm looked like a total non-effect with no
# error anywhere.  And a failed parse keeps the last good value rather than
# falling back to []: "no reading this instant" must not silently un-blacklist
# the target for that cycle.
set -u

export N_ORD=7
source /d/fabric-d2/alg1/sidecar_lib.sh

BT=/d/fabric-d2/results/bt.json
RUN=${RUN:-/tmp/push7.on}
touch "$RUN"

bl="[]"
echo "[pusher7] start (bt=$BT)"
while [ -f "$RUN" ]; do
  ensure_all_sidecars
  if [ -f "$BT" ]; then
    parsed=$(grep -oE '"blacklist" *: *\[[0-9, ]*\]' "$BT" \
             | grep -oE '\[[0-9, ]*\]' | tr -d ' ')
    if [ -n "$parsed" ]; then bl="$parsed"; fi
  fi
  for o in "${ALL_ORD[@]}"; do
    docker exec "$o" sh -c \
      "printf '%s' '{\"blacklist\":$bl,\"seq\":1,\"fail_open\":false}' > /tmp/bora-advice.json" 2>/dev/null
  done
  sleep 0.3
done
echo "[pusher7] stop"
