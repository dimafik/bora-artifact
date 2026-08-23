#!/usr/bin/env bash
# Machine-check the two enabledness facts that Liveness.tla takes as axioms.
#
#   main   : ElectEnabledInv + CampEnabledInv over the bounded model  -> must PASS
#   reach1 : ~(Inv /\ PendingCand)                                    -> must FAIL (non-vacuity)
#   reach2 : ~(Inv /\ ~HasLeader /\ ~PendingCand)                     -> must FAIL (non-vacuity)
#   mut1   : PendingCand weakened                                     -> must FAIL (hypothesis load-bearing)
#   mut2   : ~PendingCand dropped                                     -> must FAIL (hypothesis load-bearing)
#
# Usage:  bash run_enabledness.sh [main|probes|all]
set -u
cd "$(dirname "$0")" || exit 1
JAVA="$HOME/jdk17/bin/java"
OUT=./tlc_out
mkdir -p "$OUT"

run() {  # run <label> <cfg>
    local label=$1 cfg=$2
    echo "== $label ($cfg) =="
    "$JAVA" -XX:+UseParallelGC -Xmx4g -cp tla2tools.jar tlc2.TLC \
        -config "$cfg" -metadir "/tmp/tlcmeta_$label" -workers auto \
        Enabledness.tla > "$OUT/$label.log" 2>&1
    grep -aE 'is violated|Model checking completed|states generated|Finished in' \
        "$OUT/$label.log" | head -6
    echo
}

case "${1:-all}" in
  probes) ;;
  main)   run main Enabledness.cfg; exit 0 ;;
esac

run reach1 EnabledReach1.cfg
run reach2 EnabledReach2.cfg
run mut1   EnabledMut1.cfg
run mut2   EnabledMut2.cfg
[ "${1:-all}" = "all" ] && run main Enabledness.cfg
exit 0
