#!/usr/bin/env bash
# Robustness sweep for the two enabledness invariants:
#     N in {3,5,7,9}  x  MaxTerm in {2,3,5}   = 12 cells.
#
# Only N is a real axis.  The model gives each orderer one campaign --
# Campaign(i) requires state[i] = "follower" and no action in Next returns a
# node to follower -- so reachable terms never exceed 1 and MaxTerm never
# binds.  The three MaxTerm columns therefore explore identical state graphs:
# 68 / 432 / 2,368 / 12,032 distinct states at N = 3 / 5 / 7 / 9, the same in
# every column.  That identity is the expected outcome, not a bug, and it is
# why the paper calls the axis inert rather than reporting it as coverage.
#
# Every cell must report "Model checking completed. No error has been found."
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
