---------------------------- MODULE EnFalse ----------------------------
(***************************************************************************)
(* NEGATIVE CONTROL for EnTest.tla.                                        *)
(*                                                                         *)
(* EnTest showed ExpandENABLED discharging  ENABLED <<Bump>>_vars.  That is *)
(* only meaningful if the same idiom REFUSES a false statement.  If tlapm   *)
(* proves the theorems below too, ExpandENABLED is inert and the earlier    *)
(* diagnosis stands.  Every theorem here MUST FAIL.                        *)
(***************************************************************************)
EXTENDS Integers, TLAPS

VARIABLES x, y
vars == <<x, y>>

TypeOK == x \in Nat /\ y \in Nat

\* An action with contradictory constraints on the same primed variable:
\* no successor state can satisfy it, so it is never enabled.
Impossible == /\ x' = x + 1
              /\ x' = x
              /\ y' = y

\* A guarded action whose guard is false in the states TypeOK admits.
Guarded == /\ x < 0
           /\ x' = x + 1
           /\ y' = y

\* F1 and F2 MUST FAIL.
THEOREM F1 == TypeOK => ENABLED Impossible
  BY ExpandENABLED DEF TypeOK, Impossible

THEOREM F2 == TypeOK => ENABLED <<Guarded>>_vars
  BY ExpandENABLED DEF TypeOK, Guarded, vars

=============================================================================
