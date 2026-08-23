#!/usr/bin/env bash
# Wait for the in-flight campaign, then run the guarded arm.
#
# Two campaigns must never overlap: both drive the same tc sidecars and both
# pause orderers, so a second one starting early would inject one condition's
# delays while measuring another's elections. This waits on the POTENCY_DONE
# marker of the newest run directory rather than on a PID, which Git Bash does
# not report reliably for background children.
set -u

CUR="$(ls -dt /d/fabric-d2/results/potency/run_* 2>/dev/null | head -1)"
echo "waiting on: ${CUR:-<none>}"

if [ -n "$CUR" ]; then
  # bounded wait: 90 min is well past a 6-condition, 12-election campaign
  for _ in $(seq 1 5400); do
    grep -q POTENCY_DONE "$CUR/log.txt" 2>/dev/null && break
    sleep 1
  done
  if ! grep -q POTENCY_DONE "$CUR/log.txt" 2>/dev/null; then
    echo "PRIOR_RUN_DID_NOT_FINISH -- not starting the guarded arm"
    exit 1
  fi
  echo "prior run finished"
fi

# leave the cluster a moment to settle after the last unpause
sleep 20
exec bash /d/fabric-d2/alg1/potency_run.sh m500 bora 12
