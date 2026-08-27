#!/usr/bin/env bash
# R25C pilot: drive to 6 VALID runs, at most 9 attempts.
#
# Strictly sequential -- each run restarts orderers and injects netem, so two at
# once would corrupt both. Each attempt is preceded by the warm-up guard, which
# is what run 1 lacked.
set -u
LOG=/mnt/d/fabric-d2/results/r25c_runner.log
RES=/mnt/d/fabric-d2/results
HARNESS=/mnt/d/fabric-d2/alg1/r25_leader_cost3.sh
WARM="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"/warmup.sh
TARGET=6
MAXTRY=9

stamp(){ date -u +%Y-%m-%dT%H:%M:%SZ; }
log(){ echo "$*" >> "$LOG"; }

# never overlap with anything already in flight
while pgrep -f "r25_leader_cost3.sh" >/dev/null 2>&1; do sleep 30; done

valid=0; try=0
log "=== R25C pilot: target ${TARGET} valid, max ${MAXTRY} attempts ($(stamp)) ==="

while [ "$valid" -lt "$TARGET" ] && [ "$try" -lt "$MAXTRY" ]; do
  try=$((try + 1))
  log "=== attempt ${try} (valid so far ${valid}/${TARGET}) start $(stamp) ==="

  if ! bash "$WARM" >> "$LOG" 2>&1; then
    log "    attempt ${try} ABORTED before load: warm-up failed"
    sleep 60
    continue
  fi

  cd /mnt/d/fabric-d2/alg1 || exit 1
  SKIP_SETUP=1 bash "$HARNESS" 200 40 >> "$LOG" 2>&1
  rc=$?

  if [ "$rc" -eq 0 ]; then
    valid=$((valid + 1))
    log "=== attempt ${try} VALID  (valid ${valid}/${TARGET})  $(stamp) ==="
  else
    log "=== attempt ${try} INVALID rc=${rc}  $(stamp) ==="
  fi

  sleep 45          # let pumba teardown and the last restart settle
done

log "=== R25C pilot done: ${valid} valid in ${try} attempts $(stamp) ==="
log "--- r25c output directories ---"
ls -d "$RES"/r25c_2* 2>/dev/null >> "$LOG"
