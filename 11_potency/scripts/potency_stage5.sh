#!/usr/bin/env bash
# Closed-loop arm, second attempt, after both defects were fixed.
#
# The first attempt is kept on disk and is void: leader detection never
# recovered from an idle cluster, so all 200 elections recorded new_leader=0 and
# not one election actually occurred. The threshold was also calibrated on
# synthetic windows and misfired on live telemetry, flagging an unattacked
# orderer in most cycles.
set -u

RUNS=/d/fabric-d2/results/potency
LOG=$RUNS/stage5_$(date +%Y%m%d-%H%M%S).log
exec > >(tee -a "$LOG") 2>&1

echo "=== waiting for the repeated throughput run ==="
for _ in $(seq 1 7200); do
  D="$(ls -dt $RUNS/tputrep_* 2>/dev/null | head -1)"
  [ -n "$D" ] && grep -q TPUTREP_DONE "$D/log.txt" 2>/dev/null && { echo "done: $(basename "$D")"; break; }
  sleep 5
done

for _ in $(seq 1 60); do
  P=$(docker ps --filter "status=paused" --format '{{.Names}}' | grep -c orderer || true)
  [ "$P" = 0 ] && break
  echo "  waiting: $P orderer(s) paused"; sleep 5
done

# No leftover injectors: a stale qdisc would corrupt the attack-free window the
# threshold is calibrated on, and a threshold calibrated over an attack covers
# the attack.
for pre in tct tcr tcp tcc; do
  for i in $(seq 1 7); do
    docker exec "${pre}$i" tc qdisc del dev eth0 root >/dev/null 2>&1
    docker rm -f "${pre}$i" >/dev/null 2>&1
  done
done
sleep 30

echo
echo "=== closed loop, m8, 40 elections per condition ==="
bash /d/fabric-d2/alg1/potency_closed.sh 40 || echo "CLOSED_FAILED"
echo "STAGE5_DONE"
