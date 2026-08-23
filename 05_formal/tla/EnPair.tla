--------------------------- MODULE EnPair ---------------------------
(***************************************************************************)
(* Apples to apples.                                                       *)
(*                                                                         *)
(* EnBisect showed that a one-line  BY ExpandENABLED  fails even for        *)
(* BecomeLeader, the action whose lift succeeds inside Liveness.tla.  So    *)
(* the difference was never the action -- it is the PROOF SHAPE.  Adding    *)
(* full TypeOK did not help either.                                        *)
(*                                                                         *)
(* What Liveness.tla actually does is: PICK the witness out of the          *)
(* existential, prove ENABLED for that fixed instance, state the action     *)
(* implication, then close with every ENABLED fact-set at once.            *)
(*                                                                         *)
(* Below, both actions get that identical recipe, character for character.  *)
(* If ELECT closes and CAMP does not, the action really is the difference   *)
(* and we will have isolated it against a correct baseline.  If both close, *)
(* CampEnabled is solved.                                                   *)
(***************************************************************************)
EXTENDS Vanilla, TLAPS

ASSUME NAssume  == N \in Nat /\ N >= 1
ASSUME MTAssume == MaxTerm \in Nat /\ MaxTerm >= 1

ElectStep == \E i \in Orderers : BecomeLeader(i)
CampStep  == \E i \in Orderers : Campaign(i)

PendingCand  == \E i \in Orderers : state[i] = "candidate" /\ leader[currentTerm[i]] = 0
SomeFollower == \E i \in Orderers : state[i] = "follower"  /\ currentTerm[i] < MaxTerm

(***************************************************************************)
(* ELECT -- the recipe that is known to close inside Liveness.tla.         *)
(***************************************************************************)
THEOREM Elect == (TypeOK /\ PendingCand) => ENABLED <<ElectStep>>_vars
<1> SUFFICES ASSUME TypeOK, PendingCand PROVE ENABLED <<ElectStep>>_vars
    OBVIOUS
<1>1. PICK i \in Orderers : state[i] = "candidate" /\ leader[currentTerm[i]] = 0
    BY DEF PendingCand
<1>2. state \in [Orderers -> {"follower","candidate","leader"}]
    BY DEF TypeOK
<1>3. ENABLED <<BecomeLeader(i)>>_vars
    BY <1>1, <1>2, ExpandENABLED DEF BecomeLeader, vars
<1>4. <<BecomeLeader(i)>>_vars => <<ElectStep>>_vars
    BY <1>1 DEF ElectStep
<1> QED
    BY <1>1, <1>2, <1>3, <1>4, ENABLEDrules, ENABLEDaxioms, ENABLEDrewrites,
       ExpandENABLED DEF ElectStep, BecomeLeader, vars

(***************************************************************************)
(* CAMP -- the same recipe, same order, same fact-sets.                    *)
(***************************************************************************)
THEOREM Camp == (TypeOK /\ SomeFollower) => ENABLED <<CampStep>>_vars
<1> SUFFICES ASSUME TypeOK, SomeFollower PROVE ENABLED <<CampStep>>_vars
    OBVIOUS
<1>1. PICK i \in Orderers : state[i] = "follower" /\ currentTerm[i] < MaxTerm
    BY DEF SomeFollower
<1>2. state \in [Orderers -> {"follower","candidate","leader"}]
    BY DEF TypeOK
<1>3. ENABLED <<Campaign(i)>>_vars
    BY <1>1, <1>2, ExpandENABLED DEF Campaign, vars
<1>4. <<Campaign(i)>>_vars => <<CampStep>>_vars
    BY <1>1 DEF CampStep
<1> QED
    BY <1>1, <1>2, <1>3, <1>4, ENABLEDrules, ENABLEDaxioms, ENABLEDrewrites,
       ExpandENABLED DEF CampStep, Campaign, vars

=============================================================================
