#!/usr/bin/env bash
# Stage 2, run unattended after the election campaign: restore the channel,
# then measure throughput under every delay track.
#
# Waits on the guarded run's POTENCY_DONE marker rather than a PID -- Git Bash
# does not report background children reliably, and starting the channel
# restore while an orderer is paused would submit configuration transactions
# into a cluster mid-election.
set -u

RUNS=/d/fabric-d2/results/potency
LOG=$RUNS/stage2_$(date +%Y%m%d-%H%M%S).log
exec > >(tee -a "$LOG") 2>&1

echo "=== stage 2 waiting for the guarded arm ==="
for _ in $(seq 1 10800); do
  D="$(ls -dt $RUNS/run_m500_bora_* 2>/dev/null | head -1)"
  [ -n "$D" ] && grep -q POTENCY_DONE "$D/log.txt" 2>/dev/null && { echo "guarded arm done: $(basename "$D")"; break; }
  sleep 5
done

D="$(ls -dt $RUNS/run_m500_bora_* 2>/dev/null | head -1)"
if [ -z "$D" ] || ! grep -q POTENCY_DONE "$D/log.txt" 2>/dev/null; then
  echo "GUARDED_ARM_DID_NOT_FINISH -- stopping before touching the channel"
  exit 1
fi

# no orderer may be paused when configuration transactions go in
for _ in $(seq 1 60); do
  P=$(docker ps --filter "status=paused" --format '{{.Names}}' | grep -c orderer || true)
  [ "$P" = 0 ] && break
  echo "  waiting: $P orderer(s) paused"; sleep 5
done
sleep 20

echo
echo "=== restoring channel and chaincode ==="
bash /d/fabric-d2/alg1/restore_channel.sh || { echo "RESTORE_FAILED"; exit 1; }
grep -q RESTORE_DONE "$LOG" || echo "  (restore did not print RESTORE_DONE -- check above)"

echo
echo "=== throughput across all tracks ==="
bash /d/fabric-d2/alg1/potency_throughput.sh m500 180 4 || { echo "TPUT_FAILED"; exit 1; }

echo "STAGE2_DONE"
