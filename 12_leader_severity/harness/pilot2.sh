#!/usr/bin/env bash
# R25C pilot, resumable. Counts the valid runs already on disk and keeps going
# until the pre-registered pilot target is met, so an interruption costs only
# the run that was in flight.
#
# A run counts as valid when all three required arms reported a committed
# measurement. measure() prints ">>> <arm>:" only after the ledger-delta check
# passes, so the presence of all three lines is exactly the validity rule of
# PREREG_R25C section 6.
set -u
LOG=/mnt/d/fabric-d2/results/r25c_runner.log
RES=/mnt/d/fabric-d2/results
HARNESS=/mnt/d/fabric-d2/alg1/r25_leader_cost3.sh
WARM="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"/warmup.sh
TARGET=6
MAXTRY=9

stamp(){ date -u +%Y-%m-%dT%H:%M:%SZ; }
log(){ echo "$*" >> "$LOG"; }

count_valid(){
  local n=0 d
  for d in "$RES"/r25c_2*/; do
    [ -f "$d/summary.txt" ] || continue
    if grep -q '^>>> C_clean:'    "$d/summary.txt" 2>/dev/null \
    && grep -q '^>>> F_follower:' "$d/summary.txt" 2>/dev/null \
    && grep -q '^>>> L_leader:'   "$d/summary.txt" 2>/dev/null; then
      n=$((n + 1))
    fi
  done
  echo "$n"
}

# never overlap with anything already in flight
while pgrep -f "r25_leader_cost3.sh" >/dev/null 2>&1; do sleep 30; done

valid=$(count_valid)
try=0
log "=== R25C pilot RESUME: ${valid}/${TARGET} valid already on disk ($(stamp)) ==="

while [ "$valid" -lt "$TARGET" ] && [ "$try" -lt "$MAXTRY" ]; do
  try=$((try + 1))
  log "=== resume attempt ${try} (valid ${valid}/${TARGET}) start $(stamp) ==="

  if ! bash "$WARM" >> "$LOG" 2>&1; then
    log "    resume attempt ${try} ABORTED before load: warm-up failed"
    sleep 60
    continue
  fi

  cd /mnt/d/fabric-d2/alg1 || exit 1
  SKIP_SETUP=1 bash "$HARNESS" 200 40 >> "$LOG" 2>&1
  rc=$?

  before=$valid
  valid=$(count_valid)
  if [ "$valid" -gt "$before" ]; then
    log "=== resume attempt ${try} VALID  (valid ${valid}/${TARGET})  $(stamp) ==="
  else
    log "=== resume attempt ${try} INVALID rc=${rc}  $(stamp) ==="
  fi

  sleep 45          # pumba teardown and the last restart settle
done

log "=== R25C pilot RESUME done: ${valid} valid, ${try} attempts this session $(stamp) ==="
