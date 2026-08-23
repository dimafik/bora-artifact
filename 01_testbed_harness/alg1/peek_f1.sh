#!/usr/bin/env bash
ROOT=/mnt/d/fabric-d2/results/ne26_phase_f_20260610-151538
for ph in phaseF1_clean phaseF2_attack_only phaseF3_bora_active; do
  for s in 1 2 3; do
    LOG="$ROOT/$ph/caliper-${ph#phase}-seed${s}.log"
    LOG2="$ROOT/$ph/caliper-${ph#phaseF}_*-seed${s}.log"
    F=$(ls $ROOT/$ph/caliper-*-seed${s}.log 2>/dev/null | head -1)
    if [ -n "$F" ] && [ -f "$F" ]; then
      echo "=== $ph seed$s ($(basename $F)) ==="
      # Caliper report table is like:
      # | rate-600 | success | fail | TPS | min | max | avg | sent_rate |
      grep -A1 '+----------' "$F" 2>/dev/null | grep -E 'rate-[0-9]' | head -4
    fi
  done
done
