#!/usr/bin/env bash
# Definitive campaign: forty elections per condition, both arms, in sequence.
#
# Twelve was a pilot.  The comparison that decides the question is 0% against
# chance (14.3%) in the guarded arm, and at n=12 those two hypotheses give
# Wilson intervals of [0, 24%] and [5%, 45%] -- overlapping across most of their
# range.  At n=40 they are [0, 8.8%] and [7%, 29%], which separate.  The paper's
# own precedent is the same order: 0/36, reported as <=9.6%.
#
# Waits for the pilot to finish first.  Two campaigns must never overlap: both
# drive the same tc sidecars and both pause orderers, so a second one starting
# early would inject one condition's delays while measuring another's elections.
set -u

N=40
RUNS=/d/fabric-d2/results/potency

CUR="$(ls -dt $RUNS/run_* 2>/dev/null | head -1)"
if [ -n "$CUR" ] && ! grep -q POTENCY_DONE "$CUR/log.txt" 2>/dev/null; then
  echo "waiting for pilot: $(basename "$CUR")"
  for _ in $(seq 1 3600); do
    grep -q POTENCY_DONE "$CUR/log.txt" 2>/dev/null && break
    sleep 1
  done
  grep -q POTENCY_DONE "$CUR/log.txt" 2>/dev/null || { echo "PILOT_STALLED"; exit 1; }
  echo "pilot finished"
fi

sleep 20   # let the cluster settle after the last unpause

echo "######## unguarded, N=$N ########"
bash /d/fabric-d2/alg1/potency_run.sh m500 base $N || { echo "BASE_FAILED"; exit 1; }

sleep 30

echo "######## guarded, N=$N ########"
bash /d/fabric-d2/alg1/potency_run.sh m500 bora $N || { echo "BORA_FAILED"; exit 1; }

echo "CHAIN40_DONE"
