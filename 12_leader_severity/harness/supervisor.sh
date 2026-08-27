#!/usr/bin/env bash
# R25C supervisor. Detached from the session that starts it, so killing the
# Claude Code background task does not kill the campaign.
#
# Contract:
#   - drive the campaign to TARGET valid runs and then exit
#   - never run two measurements at once
#   - after any interruption, recount valid runs FROM DISK and continue
#   - never start a run while another runner or the harness is in flight
set -u
LOG=/mnt/d/fabric-d2/results/r25c_runner.log
SUP=/mnt/d/fabric-d2/results/r25c_supervisor.log
RES=/mnt/d/fabric-d2/results
HARNESS=/mnt/d/fabric-d2/alg1/r25_leader_cost3.sh
WARM="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"/warmup.sh
TARGET="${1:-6}"   # pre-registered stages: 6 (pilot), 12 (main), 18 (conditional)
MAXTRY=32          # attempts this supervisor may make, invalid ones included
IDLE=30            # seconds between liveness checks while another runner works

stamp(){ date -u +%Y-%m-%dT%H:%M:%SZ; }
slog(){ echo "[$(stamp)] $*" >> "$SUP"; }

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

# Anything that is already driving the harness, including the pilot runner this
# supervisor is meant to outlive. Its own PID is excluded.
other_runner_alive(){
  pgrep -f "r25_leader_cost3.sh" >/dev/null 2>&1 && return 0
  pgrep -f "pilot2\.sh" >/dev/null 2>&1 && return 0
  return 1
}

slog "supervisor start (pid $$), target ${TARGET}"

try=0
while :; do
  valid=$(count_valid)
  if [ "$valid" -ge "$TARGET" ]; then
    slog "target met: ${valid}/${TARGET} valid -- supervisor exiting"
    echo "=== R25C supervisor: target met, ${valid}/${TARGET} valid $(stamp) ===" >> "$LOG"
    break
  fi
  if [ "$try" -ge "$MAXTRY" ]; then
    slog "attempt ceiling ${MAXTRY} reached at ${valid}/${TARGET} -- supervisor exiting"
    break
  fi

  if other_runner_alive; then
    slog "another runner is working (${valid}/${TARGET}) -- standing by"
    sleep "$IDLE"
    continue
  fi

  try=$((try + 1))
  slog "taking over: attempt ${try}, ${valid}/${TARGET} valid"
  echo "=== R25C supervisor attempt ${try} (valid ${valid}/${TARGET}) start $(stamp) ===" >> "$LOG"

  if ! bash "$WARM" >> "$LOG" 2>&1; then
    slog "attempt ${try} aborted before load: warm-up failed"
    sleep 60
    continue
  fi

  cd /mnt/d/fabric-d2/alg1 || exit 1
  SKIP_SETUP=1 bash "$HARNESS" 200 40 >> "$LOG" 2>&1
  rc=$?
  after=$(count_valid)
  if [ "$after" -gt "$valid" ]; then
    slog "attempt ${try} VALID -> ${after}/${TARGET}"
    echo "=== R25C supervisor attempt ${try} VALID (valid ${after}/${TARGET}) $(stamp) ===" >> "$LOG"
  else
    slog "attempt ${try} INVALID rc=${rc} (still ${after}/${TARGET})"
    echo "=== R25C supervisor attempt ${try} INVALID rc=${rc} $(stamp) ===" >> "$LOG"
  fi
  sleep 45
done

slog "supervisor done"
