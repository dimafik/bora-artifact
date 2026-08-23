------------------------------ MODULE Liveness ------------------------------
(***************************************************************************)
(* Fairness-based liveness for the vanilla model (TLAPS + ExpandENABLED):    *)
(* under weak fairness of the campaign and become-leader actions, a leader   *)
(* is eventually elected:  SpecL => <>HasLeader.  This is the NON-            *)
(* probabilistic core of Proposition (liveness); the randomized-timeout RATE *)
(* (w.p.1, geometric decay) is a probabilistic property, not expressible in  *)
(* (non-probabilistic) TLA+, and is out of scope.                           *)
(***************************************************************************)
EXTENDS Vanilla, TLAPS, SequenceTheorems

HasLeader == \E i \in Orderers : state[i] = "leader"
CampStep  == \E i \in Orderers : Campaign(i)
ElectStep == \E i \in Orderers : BecomeLeader(i)
SpecL == Init /\ [][Next]_vars /\ WF_vars(CampStep) /\ WF_vars(ElectStep)

ASSUME NAssume == N \in Nat /\ N >= 1
ASSUME MTAssume == MaxTerm \in Nat /\ MaxTerm >= 1

PendingCand == \E i \in Orderers : state[i] = "candidate" /\ leader[currentTerm[i]] = 0
SomeFollower == \E i \in Orderers : state[i] = "follower" /\ currentTerm[i] < MaxTerm

\* Inductive invariant suite needed for liveness.
LeaderInv == \A t \in 0..MaxTerm : leader[t] # 0 => state[leader[t]] = "leader"
FollowerT0 == \A i \in Orderers : state[i] = "follower" => currentTerm[i] = 0
Inv == TypeOK /\ LeaderInv /\ FollowerT0

\* Invariant preservation as a single-step ACTION lemma (reused everywhere).
\* Defined-operator hypotheses (Inv) are kept in ANTECEDENT position; only raw
\* declarations (NEW i) are introduced by ASSUME, so they propagate to leaves.
\* Interval/arithmetic side-conditions are discharged by SMT, the function-
\* constructor / EXCEPT / set assembly by Zenon (no single backend does both).
\* Per-action invariant preservation, promoted to reusable lemmas (Inv in
\* ANTECEDENT so DEF works).  These are cited both by InvStep and by the
\* liveness leads-to steps below, avoiding any SUFFICES ASSUME of Inv.
LEMMA InvUnch == (Inv /\ UNCHANGED vars) => Inv'
  BY DEF Inv, TypeOK, LeaderInv, FollowerT0, Orderers, vars
LEMMA InvCamp == ASSUME NEW i \in Orderers PROVE (Inv /\ Campaign(i)) => Inv'
  <1>a. (Inv /\ Campaign(i)) => currentTerm[i] \in 0..MaxTerm  BY DEF Inv, TypeOK, Orderers
  <1>b. (Inv /\ Campaign(i)) => (currentTerm[i] + 1 \in 0..MaxTerm /\ i \in 0..N)
    BY <1>a, MTAssume, NAssume, SMT DEF Campaign, Orderers
  <1>1. (Inv /\ Campaign(i)) => TypeOK'  BY <1>b DEF Inv, Campaign, TypeOK, Orderers
  <1>2. (Inv /\ Campaign(i)) => LeaderInv'  BY DEF Inv, Campaign, LeaderInv, TypeOK, Orderers
  <1>3. (Inv /\ Campaign(i)) => FollowerT0'  BY DEF Inv, Campaign, FollowerT0, TypeOK, Orderers
  <1>4. QED BY <1>1, <1>2, <1>3 DEF Inv
LEMMA InvBecome == ASSUME NEW i \in Orderers PROVE (Inv /\ BecomeLeader(i)) => Inv'
  <1>a. (Inv /\ BecomeLeader(i)) => currentTerm[i] \in 0..MaxTerm  BY DEF Inv, TypeOK, Orderers
  <1>b. (Inv /\ BecomeLeader(i)) => i \in 0..N  BY NAssume, SMT DEF Orderers
  <1>1. (Inv /\ BecomeLeader(i)) => TypeOK'  BY <1>a, <1>b DEF Inv, BecomeLeader, TypeOK, Orderers
  <1>2. (Inv /\ BecomeLeader(i)) => LeaderInv'  BY <1>a DEF Inv, BecomeLeader, LeaderInv, TypeOK, Orderers
  <1>3. (Inv /\ BecomeLeader(i)) => FollowerT0'  BY DEF Inv, BecomeLeader, FollowerT0, TypeOK, Orderers
  <1>4. QED BY <1>1, <1>2, <1>3 DEF Inv
LEMMA InvAppend == ASSUME NEW i \in Orderers, NEW v \in Values PROVE (Inv /\ AppendEntry(i, v)) => Inv'
  <1>a. (Inv /\ AppendEntry(i, v)) => currentTerm[i] \in 0..MaxTerm  BY DEF Inv, TypeOK, Orderers
  <1>l. (Inv /\ AppendEntry(i, v)) => log[i] \in Seq([term : 0..MaxTerm, value : Values])  BY DEF Inv, TypeOK, Orderers
  <1>r. (Inv /\ AppendEntry(i, v)) =>
          [term |-> currentTerm[i], value |-> v] \in [term : 0..MaxTerm, value : Values]  BY <1>a DEF Inv, AppendEntry
  <1>s. (Inv /\ AppendEntry(i, v)) =>
          Append(log[i], [term |-> currentTerm[i], value |-> v]) \in Seq([term : 0..MaxTerm, value : Values])
    BY <1>l, <1>r, Auto
  <1>1. (Inv /\ AppendEntry(i, v)) => TypeOK'  BY <1>s DEF Inv, AppendEntry, TypeOK, Orderers
  <1>2. QED BY <1>1 DEF Inv, AppendEntry, LeaderInv, FollowerT0, TypeOK, Orderers
LEMMA InvCommit == ASSUME NEW i \in Orderers PROVE (Inv /\ Commit(i)) => Inv'
  <1>l. (Inv /\ Commit(i)) => log[i] \in Seq([term : 0..MaxTerm, value : Values])  BY DEF Inv, TypeOK, Orderers
  <1>n. (Inv /\ Commit(i)) => Len(log[i]) \in Nat  BY <1>l, Auto
  <1>ci. (Inv /\ Commit(i)) => commitIndex[i] \in Nat  BY DEF Inv, TypeOK, Orderers
  <1>g. (Inv /\ Commit(i)) => Len(log[i]) \in 1..Len(log[i])  BY <1>n, <1>ci, SMT DEF Inv, Commit, TypeOK, Orderers
  <1>v. (Inv /\ Commit(i)) => log[i][Len(log[i])] \in [term : 0..MaxTerm, value : Values]  BY <1>l, <1>g, ElementOfSeq
  <1>w. (Inv /\ Commit(i)) =>
          [index |-> Len(log[i]), value |-> log[i][Len(log[i])].value] \in [index : Nat, value : Values]  BY <1>n, <1>v, Auto
  <1>h. (Inv /\ Commit(i)) =>
          Append(history, [index |-> Len(log[i]), value |-> log[i][Len(log[i])].value]) \in Seq([index : Nat, value : Values])
    BY <1>w, Auto DEF Inv, Commit, TypeOK, Orderers
  <1>1. (Inv /\ Commit(i)) => TypeOK'  BY <1>n, <1>h DEF Inv, Commit, TypeOK, Orderers
  <1>2. QED BY <1>1 DEF Inv, Commit, LeaderInv, FollowerT0, TypeOK, Orderers
LEMMA InvStep == Inv /\ [Next]_vars => Inv'
  BY InvUnch, InvCamp, InvBecome, InvAppend, InvCommit DEF Next, vars

\* State-transition facts (EXCEPT extraction; domain comes from Inv => TypeOK).
LEMMA CampState == ASSUME NEW j \in Orderers
                   PROVE (Inv /\ Campaign(j)) => (state'[j] = "candidate" /\ leader' = leader)
  BY DEF Inv, Campaign, TypeOK, Orderers
LEMMA BecomeState == ASSUME NEW j \in Orderers PROVE (Inv /\ BecomeLeader(j)) => state'[j] = "leader"
  BY DEF Inv, BecomeLeader, TypeOK, Orderers
LEMMA CampNoLeader == ASSUME NEW j \in Orderers PROVE (Inv /\ ~HasLeader /\ Campaign(j)) => ~HasLeader'
  BY DEF Inv, Campaign, HasLeader, TypeOK, Orderers
LEMMA CampKeep == ASSUME NEW i \in Orderers, NEW j \in Orderers, i # j
                  PROVE (Inv /\ Campaign(j)) => (state'[i] = state[i] /\ currentTerm'[i] = currentTerm[i] /\ leader' = leader)
  BY DEF Inv, Campaign, TypeOK, Orderers
\* A campaigning follower j leaves any pending candidate i (#j) pending.  Witness
\* facts are kept in the ANTECEDENT (only NEW is ASSUMEd; a step ASSUME of a
\* predicate would drop it).
LEMMA CampPendW == ASSUME NEW i \in Orderers, NEW j \in Orderers
                   PROVE (Inv /\ Campaign(j) /\ state[i] = "candidate" /\ leader[currentTerm[i]] = 0)
                          => PendingCand'
  <1>1. (Inv /\ Campaign(j) /\ state[i] = "candidate" /\ leader[currentTerm[i]] = 0) => i # j
    BY DEF Campaign
  <1>2. (Inv /\ Campaign(j) /\ state[i] = "candidate" /\ leader[currentTerm[i]] = 0)
          => (state'[i] = "candidate" /\ leader'[currentTerm'[i]] = 0)
    BY <1>1, CampKeep DEF Inv, Campaign, TypeOK, Orderers
  <1>3. QED BY <1>2 DEF PendingCand
LEMMA CampPend == ASSUME NEW j \in Orderers
                  PROVE (Inv /\ PendingCand /\ Campaign(j)) => PendingCand'
  BY CampPendW DEF PendingCand

LEMMA InvInductive == SpecL => []Inv
  <1>1. Init => Inv
    <2>0. 0 \in 0..MaxTerm /\ 0 \in 0..N  BY NAssume, MTAssume, SMT
    <2>1. Init => TypeOK  BY <2>0 DEF Init, TypeOK, Orderers
    <2>2. Init => LeaderInv  BY <2>0 DEF Init, LeaderInv
    <2>3. Init => FollowerT0  BY DEF Init, FollowerT0, Orderers
    <2>4. QED BY <2>1, <2>2, <2>3 DEF Inv
  <1>2. QED BY <1>1, InvStep, PTL DEF SpecL

\* No-leader collapses the leader array to all-zero (used in both leads-to legs).
\* NB: defined-operator assumptions (Inv) are kept as ANTECEDENTS and forall is
\* introduced by TAKE -- a SUFFICES ASSUME Inv ... would not expose Inv to DEF.
LEMMA NoLeaderZero == Inv /\ ~HasLeader => \A t \in 0..MaxTerm : leader[t] = 0
  <1>1. SUFFICES \A t \in 0..MaxTerm : (Inv /\ ~HasLeader => leader[t] = 0) OBVIOUS
  <1>2. TAKE t \in 0..MaxTerm
  <1>3. Inv => leader[t] \in 0..N  BY DEF Inv, TypeOK
  <1>4. (Inv /\ leader[t] # 0) => leader[t] \in Orderers  BY <1>3, NAssume DEF Orderers
  <1>5. Inv => (leader[t] # 0 => state[leader[t]] = "leader")  BY DEF Inv, LeaderInv
  <1>6. QED BY <1>3, <1>4, <1>5 DEF HasLeader

(***************************************************************************)
(* Action enabledness.  The two facts below assert that the WF actions are   *)
(* enabled exactly when the leads-to source predicate holds: a pending        *)
(* candidate can always win, and under no-leader some follower can always     *)
(* campaign.                                                                 *)
(*                                                                           *)
(* An earlier version of this module took BOTH as axioms, on the stated       *)
(* ground that TLAPS's ENABLED-expansion was unavailable.  That was wrong.    *)
(* ExpandENABLED IS operational in this build: it discharges                  *)
(* ENABLED <<A>>_vars for an action in primed normal form, and it correctly   *)
(* REFUSES false enabledness claims (probe: an action with x' = x+1 /\ x' = x, *)
(* and one with an unsatisfiable guard, both rejected).  The earlier          *)
(* diagnosis came from a single test that bundled two obligations -- the      *)
(* ENABLED expansion and the stuttering-exclusion conjunct vars' # vars --    *)
(* into one.  Asked separately, both go through.                             *)
(*                                                                           *)
(* ElectEnabled is therefore now a PROVED THEOREM.                           *)
(*                                                                           *)
(* CampEnabled is a PROVED THEOREM as well, so this module now has NO        *)
(* axioms.  Getting there took isolating why the lift over the existential   *)
(* worked for ElectStep and not for CampStep.  It was not the action:        *)
(* a one-line BY ExpandENABLED fails for BecomeLeader too (EnBisect.tla).    *)
(* It was not context clutter, full TypeOK, or the arithmetic in Campaign's  *)
(* guard and assignment (EnCamp.tla, four variants, all fail identically).   *)
(*                                                                          *)
(* The rule is: PICK the witness out of an EXISTENTIAL PREDICATE, prove      *)
(* ENABLED for that fixed instance, state the action implication, then close *)
(* with every ENABLED fact-set at once.  ElectEnabled already had that shape *)
(* because PendingCand is an existential.  The failing CampEnabled attempt   *)
(* derived concrete facts about orderer 1 and picked from those, so the      *)
(* witness was never tied to the goal's existential the way the rules need.  *)
(* Introducing SomeFollower and picking from it closes it (EnPair.tla shows  *)
(* both actions closing under the identical recipe).                         *)
(*                                                                          *)
(* Both facts remain independently model-checked in Enabledness.tla.         *)
(***************************************************************************)
THEOREM ElectEnabled == Inv /\ PendingCand => ENABLED <<ElectStep>>_vars
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

THEOREM CampEnabled == Inv /\ ~HasLeader /\ ~PendingCand => ENABLED <<CampStep>>_vars
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

THEOREM Liveness == SpecL => <> HasLeader
<1> USE NAssume, MTAssume DEF Orderers
<1>I. SpecL => []Inv  BY InvInductive
\* Step 1: under Inv, a pending candidate leads to a leader.
<1>1. SpecL => ((Inv /\ PendingCand) ~> HasLeader)
  <2> DEFINE P == Inv /\ PendingCand /\ ~HasLeader
  <2>2. (P /\ [Next]_vars) => (P' \/ HasLeader')
    <3>U. (P /\ UNCHANGED vars) => (P' \/ HasLeader')  BY InvUnch DEF P, PendingCand, HasLeader, vars
    <3>C. ASSUME NEW j \in Orderers PROVE (P /\ Campaign(j)) => (P' \/ HasLeader')
      <4>i. (P /\ Campaign(j)) => Inv'  BY InvCamp DEF P
      <4>h. (P /\ Campaign(j)) => ~HasLeader'  BY CampNoLeader DEF P
      <4>c. (P /\ Campaign(j)) => PendingCand'  BY CampPend DEF P
      <4>7. QED BY <4>i, <4>h, <4>c DEF P
    <3>B. ASSUME NEW j \in Orderers PROVE (P /\ BecomeLeader(j)) => HasLeader'
      <4>2. (P /\ BecomeLeader(j)) => state'[j] = "leader"  BY BecomeState DEF P
      <4>3. QED BY <4>2 DEF HasLeader
    <3>A. ASSUME NEW j \in Orderers, NEW v \in Values PROVE (P /\ AppendEntry(j, v)) => (P' \/ HasLeader')
      <4>i. (P /\ AppendEntry(j, v)) => Inv'  BY InvAppend DEF P
      <4>1. QED BY <4>i DEF P, PendingCand, HasLeader, AppendEntry, Inv, TypeOK, Orderers
    <3>M. ASSUME NEW j \in Orderers PROVE (P /\ Commit(j)) => (P' \/ HasLeader')
      <4>i. (P /\ Commit(j)) => Inv'  BY InvCommit DEF P
      <4>1. QED BY <4>i DEF P, PendingCand, HasLeader, Commit, Inv, TypeOK, Orderers
    <3>6. QED BY <3>U, <3>C, <3>B, <3>A, <3>M DEF Next, vars
  <2>3. (P /\ <<ElectStep>>_vars) => HasLeader'
    <3>1. SUFFICES ASSUME NEW j \in Orderers PROVE (P /\ BecomeLeader(j)) => HasLeader'  BY DEF ElectStep
    <3>2. (P /\ BecomeLeader(j)) => state'[j] = "leader"  BY BecomeState DEF P
    <3>3. QED BY <3>2 DEF HasLeader
  <2>4. P => ENABLED <<ElectStep>>_vars  BY ElectEnabled DEF P
  <2>5. QED BY <2>2, <2>3, <2>4, PTL DEF SpecL
\* Step 2: from no leader, fairness on campaigning yields a pending candidate.
<1>2. SpecL => ((Inv /\ ~HasLeader) ~> (PendingCand \/ HasLeader))
  <2> DEFINE Q == Inv /\ ~HasLeader /\ ~PendingCand
  <2>2. (Q /\ [Next]_vars) => (Q' \/ PendingCand' \/ HasLeader')
    \* Actions stay in the GOAL antecedent (a step-level ASSUME of a defined-op
    \* application such as Campaign(j) would drop that fact); only NEW is ASSUMEd.
    <3>Z. Q => (\A t \in 0..MaxTerm : leader[t] = 0)  BY NoLeaderZero DEF Q
    <3>U. (Q /\ UNCHANGED vars) => (Q' \/ PendingCand' \/ HasLeader')  BY InvUnch DEF Q, PendingCand, HasLeader, vars
    <3>C. ASSUME NEW j \in Orderers PROVE (Q /\ Campaign(j)) => (PendingCand' \/ HasLeader')
      <4>i. (Q /\ Campaign(j)) => Inv'  BY InvCamp DEF Q
      <4>4. (Q /\ Campaign(j)) => (state'[j] = "candidate" /\ leader' = leader)  BY CampState DEF Q
      <4>2. (Q /\ Campaign(j)) => currentTerm'[j] \in 0..MaxTerm  BY <4>i DEF Inv, TypeOK, Orderers
      <4>5. (Q /\ Campaign(j)) => leader'[currentTerm'[j]] = 0  BY <4>2, <4>4, <3>Z
      <4>6. QED BY <4>4, <4>5 DEF PendingCand
    <3>B. ASSUME NEW j \in Orderers PROVE (Q /\ BecomeLeader(j)) => HasLeader'
      <4>2. (Q /\ BecomeLeader(j)) => state'[j] = "leader"  BY BecomeState DEF Q
      <4>3. QED BY <4>2 DEF HasLeader
    <3>A. ASSUME NEW j \in Orderers, NEW v \in Values PROVE (Q /\ AppendEntry(j, v)) => (Q' \/ PendingCand' \/ HasLeader')
      <4>i. (Q /\ AppendEntry(j, v)) => Inv'  BY InvAppend DEF Q
      <4>1. QED BY <4>i DEF Q, PendingCand, HasLeader, AppendEntry, Inv, TypeOK, Orderers
    <3>M. ASSUME NEW j \in Orderers PROVE (Q /\ Commit(j)) => (Q' \/ PendingCand' \/ HasLeader')
      <4>i. (Q /\ Commit(j)) => Inv'  BY InvCommit DEF Q
      <4>1. QED BY <4>i DEF Q, PendingCand, HasLeader, Commit, Inv, TypeOK, Orderers
    <3>6. QED BY <3>U, <3>C, <3>B, <3>A, <3>M DEF Next, vars
  <2>3. (Q /\ <<CampStep>>_vars) => (PendingCand' \/ HasLeader')
    <3>Z. Q => (\A t \in 0..MaxTerm : leader[t] = 0)  BY NoLeaderZero DEF Q
    <3>1. SUFFICES ASSUME NEW j \in Orderers PROVE (Q /\ Campaign(j)) => (PendingCand' \/ HasLeader')  BY DEF CampStep
    <3>i. (Q /\ Campaign(j)) => Inv'  BY InvCamp DEF Q
    <3>4. (Q /\ Campaign(j)) => (state'[j] = "candidate" /\ leader' = leader)  BY CampState DEF Q
    <3>2. (Q /\ Campaign(j)) => currentTerm'[j] \in 0..MaxTerm  BY <3>i DEF Inv, TypeOK, Orderers
    <3>5. (Q /\ Campaign(j)) => leader'[currentTerm'[j]] = 0  BY <3>2, <3>4, <3>Z
    <3>6. QED BY <3>4, <3>5 DEF PendingCand
  <2>4. Q => ENABLED <<CampStep>>_vars  BY CampEnabled DEF Q
  <2>5. QED BY <2>2, <2>3, <2>4, PTL DEF SpecL
\* Chain: from Init (Inv /\ ~HasLeader) eventually HasLeader.
<1>3. SpecL => (Inv /\ ~HasLeader ~> HasLeader)
  <2>1. SpecL => ((Inv /\ PendingCand) ~> HasLeader) BY <1>1
  <2>2. SpecL => ((Inv /\ ~HasLeader) ~> (PendingCand \/ HasLeader)) BY <1>2
  <2>3. QED BY <2>1, <2>2, <1>I, PTL
<1>4. Init => Inv /\ ~HasLeader
  BY NAssume, MTAssume DEF Init, Inv, TypeOK, LeaderInv, FollowerT0, HasLeader, Orderers
<1>5. QED BY <1>3, <1>4, <1>I, PTL DEF SpecL
=============================================================================
