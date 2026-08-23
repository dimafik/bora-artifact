--------------------------- MODULE EnLive ---------------------------
(***************************************************************************)
(* Discharge Liveness.tla's two AXIOMs as THEOREMs.                        *)
(*                                                                         *)
(* EnTest.tla showed ExpandENABLED works in this build; EnFalse.tla showed  *)
(* it refuses false statements.  So the "ENABLED is a wall" note in         *)
(* PROOF_RESULT.txt is wrong, and the real actions are in the same primed   *)
(* normal form as the toy one: unprimed guard, total assignments, UNCHANGED.*)
(*                                                                         *)
(* The one step ExpandENABLED will not do directly is the existential:      *)
(* ENABLED <<\E k : A(k)>>_vars.  That is monotonicity, and TLAPS has a     *)
(* rule for it -- but the rule needs an ACTION-LEVEL IMPLICATION as its     *)
(* hypothesis.  Stating it as a step-level ASSUME/PROVE sequent instead     *)
(* makes the rule inapplicable, which is what the earlier attempt did.      *)
(*                                                                         *)
(* Definitions copied verbatim from Liveness.tla, as Enabledness.tla does.  *)
(***************************************************************************)
EXTENDS Vanilla, TLAPS

ASSUME NAssume  == N \in Nat /\ N >= 1
ASSUME MTAssume == MaxTerm \in Nat /\ MaxTerm >= 1

HasLeader   == \E i \in Orderers : state[i] = "leader"
CampStep    == \E i \in Orderers : Campaign(i)
ElectStep   == \E i \in Orderers : BecomeLeader(i)
PendingCand == \E i \in Orderers : state[i] = "candidate" /\ leader[currentTerm[i]] = 0
LeaderInv   == \A t \in 0..MaxTerm : leader[t] # 0 => state[leader[t]] = "leader"
FollowerT0  == \A i \in Orderers : state[i] = "follower" => currentTerm[i] = 0
Inv         == TypeOK /\ LeaderInv /\ FollowerT0

(***************************************************************************)
(* 1.  ElectEnabled: a pending candidate can take BecomeLeader.            *)
(***************************************************************************)
THEOREM ElectEnabledPf == (Inv /\ PendingCand) => ENABLED <<ElectStep>>_vars
<1> SUFFICES ASSUME Inv, PendingCand PROVE ENABLED <<ElectStep>>_vars
    OBVIOUS
<1>1. PICK i \in Orderers : state[i] = "candidate" /\ leader[currentTerm[i]] = 0
    BY DEF PendingCand
<1>2. state \in [Orderers -> {"follower","candidate","leader"}]
    BY DEF Inv, TypeOK
<1>3. ENABLED <<BecomeLeader(i)>>_vars
    BY <1>1, <1>2, ExpandENABLED DEF BecomeLeader, vars
<1>4. <<BecomeLeader(i)>>_vars => <<ElectStep>>_vars
    BY <1>1 DEF ElectStep
<1> QED
    BY <1>1, <1>2, <1>3, <1>4, ENABLEDrules, ENABLEDaxioms, ENABLEDrewrites,
       ExpandENABLED DEF ElectStep, BecomeLeader, vars

(***************************************************************************)
(* 2.  CampEnabled: with no leader and no pending candidate every orderer   *)
(* is a follower at term 0, so Campaign is enabled.                        *)
(*                                                                         *)
(* No candidate can exist: LeaderInv plus ~HasLeader forces leader[t] = 0   *)
(* for every t, so any candidate would already satisfy PendingCand.        *)
(***************************************************************************)
THEOREM CampEnabledPf ==
    (Inv /\ ~HasLeader /\ ~PendingCand) => ENABLED <<CampStep>>_vars
<1> SUFFICES ASSUME Inv, ~HasLeader, ~PendingCand PROVE ENABLED <<CampStep>>_vars
    OBVIOUS
<1>1. 1 \in Orderers
    BY NAssume DEF Orderers
<1>2. state \in [Orderers -> {"follower","candidate","leader"}]
        /\ currentTerm \in [Orderers -> 0..MaxTerm]
        /\ leader \in [0..MaxTerm -> 0..N]
    BY DEF Inv, TypeOK
<1>3. \A t \in 0..MaxTerm : leader[t] = 0
    <2> SUFFICES ASSUME NEW t \in 0..MaxTerm, leader[t] # 0 PROVE FALSE
        OBVIOUS
    <2>1. state[leader[t]] = "leader"
        BY DEF Inv, LeaderInv
    <2>2. leader[t] \in Orderers
        BY <1>2 DEF Orderers
    <2> QED
        BY <2>1, <2>2 DEF HasLeader
<1>4. state[1] # "leader"
    BY <1>1 DEF HasLeader
<1>5. state[1] # "candidate"
    <2> SUFFICES ASSUME state[1] = "candidate" PROVE FALSE
        OBVIOUS
    <2>1. currentTerm[1] \in 0..MaxTerm
        BY <1>1, <1>2
    <2>2. leader[currentTerm[1]] = 0
        BY <1>3, <2>1
    <2> QED
        BY <1>1, <2>2 DEF PendingCand
<1>6. state[1] = "follower"
    BY <1>1, <1>2, <1>4, <1>5
<1>7. currentTerm[1] = 0
    BY <1>1, <1>6 DEF Inv, FollowerT0
<1>8. currentTerm[1] < MaxTerm
    BY <1>7, MTAssume
<1>9. PICK k \in Orderers : state[k] = "follower" /\ currentTerm[k] < MaxTerm
    BY <1>1, <1>6, <1>8
<1>10. state \in [Orderers -> {"follower","candidate","leader"}]
         /\ currentTerm \in [Orderers -> 0..MaxTerm]
    BY <1>2
<1>10a. currentTerm[k] \in 0..MaxTerm /\ currentTerm[k] + 1 # currentTerm[k]
    BY <1>9, <1>10, MTAssume, SMT
<1>10b. state[k] # "candidate" /\ state[k] # "leader"
    BY <1>9
<1>11. ENABLED <<Campaign(k)>>_vars
    BY <1>9, <1>10, ExpandENABLED DEF Campaign, vars
<1>12. <<Campaign(k)>>_vars => <<CampStep>>_vars
    BY <1>9 DEF CampStep
<1> QED
    BY <1>9, <1>10, <1>10a, <1>10b, NAssume, MTAssume, ExpandENABLED
       DEF CampStep, Campaign, vars, Orderers

=============================================================================
