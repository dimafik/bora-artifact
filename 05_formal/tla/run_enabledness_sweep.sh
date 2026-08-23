#!/usr/bin/env bash
# Robustness sweep for the two enabledness invariants: vary N and MaxTerm so the
# result is not tied to one bounded instance.  Every cell must report
# "Model checking completed. No error has been found."
set -u
cd "$(dirname "$0")" || exit 1
JAVA="$HOME/jdk17/bin/java"
OUT=./tlc_out
mkdir -p "$OUT"

printf '%-6s %-8s %-10s %-12s %s\n' N MaxTerm states depth verdict
for n in 3 5 7 9; do
  for mt in 2 3 5; do
    cfg="$OUT/sweep_N${n}_T${mt}.cfg"
    cat > "$cfg" <<EOF
SPECIFICATION Spec
CONSTANTS
    N = $n
    F = 2
    MaxTerm = $mt
    Values = {v1, v2}
CONSTRAINT StateConstraint
INVARIANTS
    ElectEnabledInv
    CampEnabledInv
CHECK_DEADLOCK FALSE
EOF
    log="$OUT/sweep_N${n}_T${mt}.log"
    "$JAVA" -XX:+UseParallelGC -Xmx4g -cp tla2tools.jar tlc2.TLC \
        -config "$cfg" -metadir "/tmp/tlcsw_${n}_${mt}" -workers auto \
        Enabledness.tla > "$log" 2>&1
    st=$(grep -aoE '[0-9]+ distinct states' "$log" | head -1 | grep -oE '[0-9]+')
    dp=$(grep -aoE 'state graph search is [0-9]+' "$log" | head -1 | grep -oE '[0-9]+')
    if grep -aq 'No error has been found' "$log"; then v=PASS
    elif grep -aq 'is violated' "$log"; then v=VIOLATED
    else v=ERROR; fi
    printf '%-6s %-8s %-10s %-12s %s\n' "$n" "$mt" "${st:-?}" "${dp:-?}" "$v"
  done
done
