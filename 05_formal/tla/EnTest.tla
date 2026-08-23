---------------------------- MODULE EnTest ----------------------------
(***************************************************************************)
(* Minimal probe: does this tlapm build expand ENABLED at all, and does the *)
(* angle-bracket form <<A>>_vars behave differently from bare A?            *)
(*                                                                         *)
(* PROOF_RESULT.txt records that  ENABLED <<x' = x+1>>_vars  failed under   *)
(* every backend, and concludes ENABLED expansion is unavailable.  But that *)
(* test conflates two obligations: expanding ENABLED, and discharging the   *)
(* stuttering-exclusion conjunct  vars' # vars.  This file separates them.  *)
(***************************************************************************)
EXTENDS Integers, TLAPS

VARIABLES x, y
vars == <<x, y>>

TypeOK == x \in Nat /\ y \in Nat

Bump == /\ x' = x + 1
        /\ y' = y

\* (1) bare ENABLED, no angle brackets -- the easier obligation
THEOREM T1 == TypeOK => ENABLED Bump
  BY ExpandENABLED DEF TypeOK, Bump

\* (2) the action provably moves vars, stated separately
THEOREM T2 == TypeOK /\ Bump => vars' # vars
  BY DEF TypeOK, Bump, vars

\* (3) the full angle-bracket form, which is what WF1 actually needs
THEOREM T3 == TypeOK => ENABLED <<Bump>>_vars
  BY ExpandENABLED DEF TypeOK, Bump, vars

=============================================================================
