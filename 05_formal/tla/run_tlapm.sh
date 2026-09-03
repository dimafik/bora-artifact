#!/usr/bin/env bash
# Re-run every TLAPS proof this paper claims, from scratch, and write tlapm's own
# output to tlapm_out/.
#
# PROOF_RESULT.txt records what tlapm reported. This script is how you check that
# record against the tool rather than against us.
#
#   bash run_tlapm.sh              # uses ~/tlaps/bin/tlapm
#   TLAPM=/path/to/tlapm bash run_tlapm.sh
#
# --cleanfp discards the fingerprint cache, so every obligation is discharged
# again rather than read back from a previous run. The cache (.tlacache/) is not
# shipped for the same reason: it would let this script pass without proving
# anything.
#
# EnFalse is a NEGATIVE control and is EXPECTED to fail 2 of its 4 obligations.
# It exists to show the ENABLED tactic refuses false statements; a run in which
# EnFalse passes would mean the tactic is inert and the positive results are
# worthless. Its non-zero exit is the correct outcome.
set -u
cd "$(dirname "$0")" || exit 1
TLAPM="${TLAPM:-$HOME/tlaps/bin/tlapm}"

if [ ! -x "$TLAPM" ]; then
  echo "tlapm not found at $TLAPM -- set TLAPM=/path/to/tlapm" >&2
  exit 1
fi
echo "tlapm $("$TLAPM" --version)"
mkdir -p tlapm_out

# module            expected      what the paper claims from it
MODULES="
BORA_proof         48   safety refinement, unbounded (Theorem 1)
BORA_pv_proof      48   safety refinement, per-voter blacklist
BORA_pv_excl       64   exclusion under an honest quorum (Proposition 7)
Liveness          311   fairness-based <>leader, no axioms
EnTest              5   positive control: ENABLED expansion works
EnPair             36   both actions close under one recipe
EnCampFull         59   CampEnabled, final form
EnFalse             2   NEGATIVE control: 2 of 4 must FAIL
"

rc=0
printf '\n%-18s %8s %8s %6s  %s\n' MODULE EXPECTED PROVED EXIT RESULT
printf '%.0s-' $(seq 1 78); printf '\n'

echo "$MODULES" | while read -r m want _rest; do
  [ -n "${m:-}" ] || continue
  "$TLAPM" --cleanfp "$m.tla" > "tlapm_out/$m.log" 2>&1
  exit_code=$?
  got=$(grep -oE '[0-9]+ obligations proved' "tlapm_out/$m.log" | grep -oE '^[0-9]+')
  [ -n "$got" ] || got=$(grep -oE '[0-9]+/[0-9]+ obligations failed' "tlapm_out/$m.log" | head -1)
  if [ "$m" = "EnFalse" ]; then
    # the negative control passes this script by failing tlapm
    if [ "$exit_code" -ne 0 ]; then verdict="OK (refused, as designed)";
    else verdict="*** BROKEN: negative control was proved ***"; fi
  elif [ "$exit_code" -eq 0 ] && [ "$got" = "$want" ]; then
    verdict="OK"
  else
    verdict="*** MISMATCH ***"
  fi
  printf '%-18s %8s %8s %6s  %s\n' "$m" "$want" "${got:-none}" "$exit_code" "$verdict"
done

cat <<'TAIL'

Full transcripts are in tlapm_out/. Liveness.tla additionally claims to use no
axioms; check that directly:

    grep -c AXIOM Liveness.tla        # expected: 0

The probabilistic election rate is not a TLA+ property and is verified in PRISM
instead -- see ../prism/PRISM_RESULT.txt.
TAIL
exit $rc
