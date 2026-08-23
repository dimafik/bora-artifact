#!/usr/bin/env bash
# Repeated throughput, queued behind the closed-loop arm.
#
# Waits on CLOSED_DONE rather than a PID.  The two must not overlap: the closed
# loop scores live RTT telemetry, and a second campaign injecting its own delays
# into the same orderers would feed the detector another condition's traffic
# while it is being measured on this one.
set -u

RUNS=/d/fabric-d2/results/potency
LOG=$RUNS/stage4_$(date +%Y%m%d-%H%M%S).log
exec > >(tee -a "$LOG") 2>&1

echo "=== stage 4 waiting for the closed-loop arm ==="
for _ in $(seq 1 7200); do
  D="$(ls -dt $RUNS/closed_m8_* 2>/dev/null | head -1)"
  [ -n "$D" ] && grep -q CLOSED_DONE "$D/log.txt" 2>/dev/null && { echo "closed-loop done: $(basename "$D")"; break; }
  sleep 5
done

D="$(ls -dt $RUNS/closed_m8_* 2>/dev/null | head -1)"
if [ -z "$D" ] || ! grep -q CLOSED_DONE "$D/log.txt" 2>/dev/null; then
  echo "CLOSED_ARM_DID_NOT_FINISH -- not starting the repeats"
  exit 1
fi

for _ in $(seq 1 60); do
  P=$(docker ps --filter "status=paused" --format '{{.Names}}' | grep -c orderer || true)
  [ "$P" = 0 ] && break
  echo "  waiting: $P orderer(s) paused"; sleep 5
done
sleep 30

echo
echo "=== repeated throughput: 4 passes, rotated order ==="
bash /d/fabric-d2/alg1/potency_throughput_rep.sh 4 m500 180 4 1.0 || echo "TPUTREP_FAILED"
echo "STAGE4_DONE"
