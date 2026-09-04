#!/usr/bin/env bash
# B-20, continued: the three runs the first sweep did not finish.
#
# The first attempt completed N=7, 9 and 11 and got three of four seeds into
# N=15 before it died. It died because the driver was a child of the shell that
# launched it, so when that shell went away the driver and its harness went with
# it -- while the advisor, which had been started with setsid, carried on alone
# and made the whole thing look alive. This script is launched with setsid for
# that reason, and the launcher waits a few seconds before exiting so the detach
# actually completes; without that pause the new session is torn down before it
# takes.
#
# N=15 is run again from scratch rather than resumed at seed 4: the partial log
# is kept as partial_N15_run4.log, out of the aggregator's glob, because mixing
# three seeds from one cluster bring-up with one from another is not the same
# experiment.
set -u
cd /mnt/d/fabric-d2 || exit 1

RES=/mnt/d/fabric-d2/results
OUT=${1:?need the sweep dir to continue}
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
  if ! tail -c +$((before + 1)) "$RES/predictor_daemon_meanrtt.log" 2>/dev/null \
       | grep -q "meanrtt daemon start .*N=$1 f=$2 "; then
    say "  ADVISOR FAILED for N=$1: no start banner"
    tail -5 "$OUT/advisor_N$1.out" >> "$LOG" 2>&1
    return 1
  fi
  say "  advisor up: $(tail -1 "$RES/predictor_daemon_meanrtt.log" | cut -c1-90)"
  return 0
}

say "=== resume: N=15, 21, 21 ==="

run_one(){   # $1 = N, $2 = run index
  local N=$1 idx=$2 F=$(( ($1 - 1) / 2 ))
  say "=== run $idx/6: N=$N f=$F ==="
  if ! start_advisor "$N" "$F"; then
    say "  advisor failed; skipping N=$N"
    return 1
  fi
  say "  bt.json age $(( $(date +%s) - $(stat -c %Y "$RES/bt.json") ))s"
  say "  running x1_closedloop.sh $N 4 10 200"
  bash /mnt/d/fabric-d2/alg1/x1_closedloop.sh "$N" 4 10 200 >"$OUT/x1_N${N}_run${idx}.log" 2>&1
  local rc=$?
  if [ $rc -ne 0 ]; then
    say "  HARNESS EXIT $rc for N=$N (run $idx) -- see x1_N${N}_run${idx}.log"
  else
    say "  run $idx/6 done: $(grep -ac 's[0-9]*: target' "$OUT/x1_N${N}_run${idx}.log") result lines"
  fi
  return 0
}

run_one 15 4
run_one 21 5
run_one 21 6

pkill -f "predictor_daemon_meanrtt_wsl.py" 2>/dev/null
say "resume complete"
