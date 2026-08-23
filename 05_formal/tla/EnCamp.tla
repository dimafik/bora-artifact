---------------------------- MODULE EnCamp ----------------------------
(***************************************************************************)
(* Four attempts at the one obligation still open in Liveness.tla:          *)
(*                                                                         *)
(*     ENABLED <<CampStep>>_vars   where CampStep == \E i : Campaign(i)     *)
(*                                                                         *)
(* The identical lift succeeds for ElectStep, so the content is not the     *)
(* problem.  Two hypotheses for why Campaign fails where BecomeLeader does  *)
(* not:                                                                    *)
(*                                                                         *)
(*   H1 CONTEXT CLUTTER.  ElectEnabled reaches its QED with two facts in    *)
(*      scope.  CampEnabled reaches its QED with eight, because deriving    *)
(*      "everyone is a follower at term 0" takes eight steps.  Automated    *)
(*      backends do worse, not better, with irrelevant hypotheses.          *)
(*                                                                         *)
(*   H2 MIXED ARITHMETIC.  Campaign's witness needs                         *)
(*      [currentTerm EXCEPT ![k] = currentTerm[k] + 1], an arithmetic term  *)
(*      inside a function constructor.  PROOF_RESULT.txt already records    *)
(*      that no single backend does both: SMT for arithmetic, Zenon for     *)
(*      constructors.  BecomeLeader's witness has no arithmetic.            *)
(*                                                                         *)
(* Each theorem below isolates one variant.  Whichever closes gets lifted   *)
(* back into Liveness.tla.                                                  *)
(***************************************************************************)
EXTENDS Vanilla, TLAPS

ASSUME NAssume  == N \in Nat /\ N >= 1
ASSUME MTAssume == MaxTerm \in Nat /\ MaxTerm >= 1

CampStep == \E i \in Orderers : Campaign(i)

Ready(k) == /\ state \in [Orderers -> {"follower","candidate","leader"}]
            /\ currentTerm \in [Orderers -> 0..MaxTerm]
            /\ state[k] = "follower"
            /\ currentTerm[k] < MaxTerm

(***************************************************************************)
(* V1.  H1 alone: minimal context, direct expansion.                       *)
(***************************************************************************)
THEOREM V1 == ASSUME NEW k \in Orderers
              PROVE  Ready(k) => ENABLED <<CampStep>>_vars
  BY ExpandENABLED DEF Ready, CampStep, Campaign, vars

(***************************************************************************)
(* V2.  H1 with the constants in scope, in case the interval reasoning      *)
(* needs them.                                                             *)
(***************************************************************************)
THEOREM V2 == ASSUME NEW k \in Orderers
              PROVE  Ready(k) => ENABLED <<CampStep>>_vars
  BY NAssume, MTAssume, ExpandENABLED DEF Ready, CampStep, Campaign, vars, Orderers

(***************************************************************************)
(* V3.  H1 plus the two-step shape that worked for ElectStep: fix the       *)
(* witness first, then lift over the existential.                          *)
(***************************************************************************)
THEOREM V3 == ASSUME NEW k \in Orderers
              PROVE  Ready(k) => ENABLED <<CampStep>>_vars
<1> SUFFICES ASSUME Ready(k) PROVE ENABLED <<CampStep>>_vars
    OBVIOUS
<1>1. ENABLED <<Campaign(k)>>_vars
    BY ExpandENABLED DEF Ready, Campaign, vars
<1>2. <<Campaign(k)>>_vars => <<CampStep>>_vars
    BY DEF CampStep
<1> QED
    BY <1>1, <1>2, ENABLEDrules

(***************************************************************************)
(* V4.  H2: hand the backend the disequality and the arithmetic separately, *)
(* so the ENABLED goal is not asked to derive them alongside the witness.   *)
(***************************************************************************)
THEOREM V4 == ASSUME NEW k \in Orderers
              PROVE  Ready(k) => ENABLED <<CampStep>>_vars
<1> SUFFICES ASSUME Ready(k) PROVE ENABLED <<CampStep>>_vars
    OBVIOUS
<1>1. k \in DOMAIN state /\ k \in DOMAIN currentTerm
    BY DEF Ready
<1>2. [state EXCEPT ![k] = "candidate"] # state
    <2>1. [state EXCEPT ![k] = "candidate"][k] = "candidate"
        BY <1>1
    <2> QED
        BY <2>1 DEF Ready
<1>3. currentTerm[k] \in Nat
    BY MTAssume DEF Ready
<1>4. currentTerm[k] + 1 # currentTerm[k]
    BY <1>3
<1> QED
    BY <1>1, <1>2, <1>3, <1>4, ExpandENABLED DEF Ready, CampStep, Campaign, vars

=============================================================================
