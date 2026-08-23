------------------------- MODULE EnCampFull -------------------------
(***************************************************************************)
(* The complete CampEnabled, assembled from what EnPair.tla established.    *)
(*                                                                         *)
(* The lift over the existential works when the witness is PICKed out of an *)
(* EXISTENTIAL PREDICATE, exactly as ElectEnabled picks its candidate out   *)
(* of PendingCand.  The earlier attempt failed because it derived concrete  *)
(* facts about orderer 1 and picked from those instead, so the goal's       *)
(* existential and the witness were never connected the same way.          *)
(*                                                                         *)
(* So the proof splits in two:                                             *)
(*   CampEnabledCore : (TypeOK /\ SomeFollower) => ENABLED <<CampStep>>_vars *)
(*   CampEnabled     : the hypothesis of the liveness argument implies      *)
(*                     SomeFollower, with orderer 1 as the witness.        *)
(***************************************************************************)
EXTENDS Vanilla, TLAPS

ASSUME NAssume  == N \in Nat /\ N >= 1
ASSUME MTAssume == MaxTerm \in Nat /\ MaxTerm >= 1

HasLeader    == \E i \in Orderers : state[i] = "leader"
CampStep     == \E i \in Orderers : Campaign(i)
PendingCand  == \E i \in Orderers : state[i] = "candidate" /\ leader[currentTerm[i]] = 0
SomeFollower == \E i \in Orderers : state[i] = "follower"  /\ currentTerm[i] < MaxTerm
LeaderInv    == \A t \in 0..MaxTerm : leader[t] # 0 => state[leader[t]] = "leader"
FollowerT0   == \A i \in Orderers : state[i] = "follower" => currentTerm[i] = 0
Inv          == TypeOK /\ LeaderInv /\ FollowerT0

LEMMA CampEnabledCore == (TypeOK /\ SomeFollower) => ENABLED <<CampStep>>_vars
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

(***************************************************************************)
(* With no leader and no pending candidate, orderer 1 must be a follower at *)
(* term 0.  LeaderInv plus ~HasLeader forces leader[t] = 0 for every t, so  *)
(* a candidate would already satisfy PendingCand.                          *)
(***************************************************************************)
THEOREM CampEnabled ==
    Inv /\ ~HasLeader /\ ~PendingCand => ENABLED <<CampStep>>_vars
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
<1>9. SomeFollower
    BY <1>1, <1>6, <1>8 DEF SomeFollower
<1> QED
    BY <1>9, CampEnabledCore DEF Inv

=============================================================================
