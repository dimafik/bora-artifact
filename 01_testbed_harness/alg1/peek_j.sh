#!/usr/bin/env bash
ROOT=$(ls -dt /mnt/d/fabric-d2/results/ne26_phase_j_* 2>/dev/null | head -1)
for ph in phaseJ1_clean phaseJ2_attack_only phaseJ3_bora_active; do
  echo "=== $ph ==="
  printf "%-6s %-8s %-8s %-8s %-10s\n" "seed" "rate-600" "rate-700" "rate-800" "rate-900"
  for s in 1 2 3; do
    F=$(ls $ROOT/$ph/caliper-*-seed${s}.log 2>/dev/null | head -1)
    if [ -z "$F" ] || [ ! -f "$F" ]; then
      printf "%-6s %-8s\n" "$s" "MISSING"
      continue
    fi
    r600=$(grep -E '\| rate-600 \|' "$F" 2>/dev/null | head -1 | awk -F'|' '{gsub(/ /,"",$5); print $5}')
    r700=$(grep -E '\| rate-700 \|' "$F" 2>/dev/null | head -1 | awk -F'|' '{gsub(/ /,"",$5); print $5}')
    r800=$(grep -E '\| rate-800 \|' "$F" 2>/dev/null | head -1 | awk -F'|' '{gsub(/ /,"",$5); print $5}')
    r900=$(grep -E '\| rate-900 \|' "$F" 2>/dev/null | head -1 | awk -F'|' '{gsub(/ /,"",$5); print $5}')
    printf "%-6s %-8s %-8s %-8s %-10s\n" "$s" "${r600:-?}" "${r700:-?}" "${r800:-?}" "${r900:-?}"
  done
done
