#!/usr/bin/env bash
# Detached launcher for the R1-3 full run.
#
# Two traps this exists to avoid, both of which cost a restart today:
#
#  1. `pkill -f r13_` matches the launching shell's OWN command line (it contains
#     that string), so the shell kills itself and nothing after it runs -- with
#     no error, because the shell is gone before it can report one.
#  2. `pgrep -f r13_authority.sh` likewise matches the checking shell, so it
#     answers ALIVE whether or not the run exists.  Liveness is checked here by
#     the log file growing, which only the real run can do.
#
#   r13_launch.sh <N> <seeds> <dur> <rates...>
set -u
D=/mnt/d/fabric-d2
LOG="$D/results/r13_full_$(date +%m%d-%H%M%S).log"
echo "$LOG" > "$D/results/r13_current.log.path"

setsid nohup timeout 16200 bash "$D/alg1/r13_authority.sh" "$@" \
  > "$LOG" 2>&1 < /dev/null &
pid=$!
disown 2>/dev/null || true
echo "launched pid=$pid log=$LOG"
