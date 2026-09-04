#!/usr/bin/env bash
# B-20: the closed-loop sweep again, with a zero-parameter detector in the
# advisor's place.
#
# The question is whether the 0/240 exclusion the paper reports is a property of
# the envelope -- the cap |B_t| < f - r, the fail-open counter and the two
# guards -- or of the 141k-parameter model that fills it. Same harness, same
# forced elections, same arms; only the function that turns a telemetry window
# into a score is different.
#
# The six runs mirror the shipped campaign exactly: N = 7, 9, 11, 15, 21, 21,
# four seeds of ten elections each, so each arm accumulates 240 forced
# elections and the Wilson bound is comparable to the published one rather than
# six times looser.
#
# The advisor runs WSL-side and is started here with setsid. It is deliberately
# not started through PowerShell: Start-Process hands the daemon a handle that
# WSL's interop shim then waits on, so the caller blocks forever on a process
# that is meant to outlive it. The first launch of this sweep died that way,
# five minutes in, with the driver in do_wait and no harness ever invoked.
set -u
cd /mnt/d/fabric-d2 || exit 1

RES=/mnt/d/fabric-d2/results
OUT=$RES/b20_sweep_$(date +%Y%m%d-%H%M%S)
mkdir -p "$OUT"
LOG="$OUT/driver.log"

say(){ echo "[$(date +%H:%M:%S)] $*" >> "$LOG"; }

start_advisor(){   # $1 = N, $2 = F
  pkill -f "predictor_daemon_meanrtt_wsl.py" 2>/dev/null
  sleep 1
  local before=0
  [ -f "$RES/predictor_daemon_meanrtt.log" ] && before=$(stat -c %s "$RES/predictor_daemon_meanrtt.log")
  setsid nohup python3 /mnt/d/fabric-d2/alg1/predictor_daemon_meanrtt_wsl.py 0.65 "$1" "$2" 50 \
      >"$OUT/advisor_N$1.out" 2>&1 < /dev/null &
  sleep 6
  # Liveness is not evidence the right advisor started. Require the banner it
  # writes itself, naming this N and f -- the check that would have caught the
  # N=9 run that spent an hour replaying a previous N's blacklist.
  if ! tail -c +$((before + 1)) "$RES/predictor_daemon_meanrtt.log" 2>/dev/null \
       | grep -q "meanrtt daemon start .*N=$1 f=$2 "; then
    say "  ADVISOR FAILED for N=$1: no start banner"
    tail -5 "$OUT/advisor_N$1.out" >> "$LOG" 2>&1
    return 1
  fi
  say "  advisor up: $(tail -1 "$RES/predictor_daemon_meanrtt.log" | cut -c1-90)"
  return 0
}

say "B-20 sweep start: zero-parameter mean-RTT detector in the advisor slot"
say "output: $OUT"

RUNS="7 9 11 15 21 21"
i=0
for N in $RUNS; do
  i=$((i+1))
  F=$(( (N - 1) / 2 ))
  say "=== run $i/6: N=$N f=$F ==="

  if ! start_advisor "$N" "$F"; then
    say "  stopping the sweep here (runs completed: $((i-1))/6)"
    exit 1
  fi

  age=$(( $(date +%s) - $(stat -c %Y "$RES/bt.json") ))
  say "  bt.json age ${age}s"

  say "  running x1_closedloop.sh $N 4 10 200"
  bash /mnt/d/fabric-d2/alg1/x1_closedloop.sh "$N" 4 10 200 >"$OUT/x1_N${N}_run${i}.log" 2>&1
  rc=$?
  if [ $rc -ne 0 ]; then
    say "  HARNESS EXIT $rc for N=$N (run $i) -- see x1_N${N}_run${i}.log"
    say "  continuing to the next N; a partial sweep is still evidence, and"
    say "  stopping would waste the runs already completed"
  else
    say "  run $i/6 done: $(grep -c 's[0-9]*:' "$OUT/x1_N${N}_run${i}.log") result lines"
  fi
done

pkill -f "predictor_daemon_meanrtt_wsl.py" 2>/dev/null
say "sweep complete"

{
  echo "# B-20 zero-parameter detector sweep"
  echo "# arm C carries the mean-RTT threshold; arms A and B are unchanged"
  echo
  for f in "$OUT"/x1_N*_run*.log; do
    [ -f "$f" ] || continue
    echo "== $(basename "$f")"
    grep -a "s[0-9]*: target" "$f"
    echo
  done
} > "$OUT/collected.txt" 2>&1
say "wrote $OUT/collected.txt"
