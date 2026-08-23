#!/usr/bin/env bash
# Start the predictor daemon for a given N and wait until it proves it is up.
#
# WHY THIS EXISTS.  `powershell -File restart_daemon.ps1` invoked from bash does
# not return while the daemon it launched is alive -- the shell waits on the
# child. The N=9 chain only got past it because the daemon had failed to start,
# so there was nothing to wait for: the one case that should have blocked the run
# was the only case that let it through.
#
# So the launcher is backgrounded, and readiness is confirmed from the daemon's
# own start banner in predictor_daemon.log. That banner is written by the daemon
# after it has loaded the model, so it is evidence of a working daemon for THIS
# N, not merely of a process that exists.
#
#   start_daemon.sh 9 4
set -u

N="${1:?need N}"; F="${2:?need f}"
LOG=/mnt/d/fabric-d2/results/predictor_daemon.log
PS1F='D:\fabric-d2\alg1\restart_daemon.ps1'

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$PS1F" "$N" "$F" \
  >/tmp/restart_daemon.out 2>&1 &
LAUNCHER=$!

for _ in $(seq 1 40); do
  if tail -40 "$LOG" 2>/dev/null | grep -q "daemon start .*N=$N f=$F "; then
    echo "DAEMON_UP N=$N f=$F"
    exit 0
  fi
  # the launcher exiting early with no banner means it failed outright
  if ! kill -0 "$LAUNCHER" 2>/dev/null; then
    if ! tail -40 "$LOG" 2>/dev/null | grep -q "daemon start .*N=$N f=$F "; then
      echo "DAEMON_FAILED N=$N -- launcher exited without a start banner"
      cat /tmp/restart_daemon.out 2>/dev/null
      exit 1
    fi
  fi
  sleep 2
done

echo "DAEMON_TIMEOUT N=$N -- no start banner after 80s"
cat /tmp/restart_daemon.out 2>/dev/null
exit 1
