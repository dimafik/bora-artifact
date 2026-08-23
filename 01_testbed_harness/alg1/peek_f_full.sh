#!/usr/bin/env bash
# Parse Caliper logs for all 9 runs of Phase F.
ROOT=/mnt/d/fabric-d2/results/ne26_phase_f_20260610-151538
for ph in phaseF1_clean phaseF2_attack_only phaseF3_bora_active; do
  echo "=========================================="
  echo "$ph"
  echo "=========================================="
  printf "%-10s %-8s %-8s %-8s %-10s\n" "seed" "rate-600" "rate-700" "rate-800" "rate-900"
  for s in 1 2 3; do
    LOG=$(ls $ROOT/$ph/caliper-*-seed${s}.log 2>/dev/null | head -1)
    if [ -z "$LOG" ] || [ ! -f "$LOG" ]; then
      printf "%-10s %-8s\n" "$s" "MISSING"
      continue
    fi
    # Extract TPS values for each rate
    r600=$(grep -E '\| rate-600 \|' "$LOG" 2>/dev/null | head -1 | awk -F'|' '{gsub(/ /,"",$5); print $5}')
    r700=$(grep -E '\| rate-700 \|' "$LOG" 2>/dev/null | head -1 | awk -F'|' '{gsub(/ /,"",$5); print $5}')
    r800=$(grep -E '\| rate-800 \|' "$LOG" 2>/dev/null | head -1 | awk -F'|' '{gsub(/ /,"",$5); print $5}')
    r900=$(grep -E '\| rate-900 \|' "$LOG" 2>/dev/null | head -1 | awk -F'|' '{gsub(/ /,"",$5); print $5}')
    printf "%-10s %-8s %-8s %-8s %-10s\n" "$s" "${r600:-?}" "${r700:-?}" "${r800:-?}" "${r900:-?}"
  done
done
