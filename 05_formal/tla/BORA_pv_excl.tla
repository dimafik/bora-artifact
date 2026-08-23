------------------------- MODULE BORA_pv_excl -------------------------
(***************************************************************************)
(* Proposition (per-voter exclusion under quorum agreement), mechanised.    *)
(*                                                                         *)
(* BORA_pv_proof.tla establishes the SAFETY half of the per-voter story:   *)
(* the per-voter spec refines vanilla Raft, so every Raft invariant is      *)
(* inherited no matter how far the voters' views diverge. That half never   *)
(* needed the voters to agree. This module does the other half, the one     *)
(* that does: if a quorum of voters holds candidate i, i cannot acquire     *)
(* leadership.                                                             *)
(*                                                                         *)
(* The paper stated this as an analytical argument, on the grounds that     *)
(* advice is only eventually consistent across voters. Eventual consistency *)
(* is why the quorum hypothesis is a hypothesis rather than a theorem, but  *)
(* it is not a reason the CONDITIONAL cannot be checked: given the quorum   *)
(* agreement, exclusion follows from the vote-grant guard alone. That       *)
(* conditional is what is proved here, and it is exactly what the           *)
(* proposition claims.                                                     *)
(*                                                                         *)
(* Note the scope honestly: this says nothing about whether a quorum ever   *)
(* DOES agree within an election window. That is a deployment timing        *)
(* question, measured rather than proved, and it is why the paper reports   *)
(* exclusion empirically as well.                                          *)
(***************************************************************************)
EXTENDS BORA_pv, TLAPS, FiniteSets, Integers, Sequences

(***************************************************************************)
(* The hypothesis of the proposition, read off the current state: some      *)
(* quorum of voters all hold i in their own local blacklist.               *)
(***************************************************************************)
QuorumHolds(i) ==
    \E Q \in SUBSET Orderers : IsQuorum(Q) /\ \A j \in Q : i \in blacklist[j]

(***************************************************************************)
(* Acquisition, as a step: some term that had no leader now has i. This is  *)
(* deliberately about ACQUIRING leadership, not about holding it, because   *)
(* that is what the guard governs and what the Active-Leader Rule leaves    *)
(* alone for the incumbent.                                                *)
(***************************************************************************)
Acquires(i) ==
    \E t \in 0..MaxTerm : leader[t] = 0 /\ leader'[t] = i

ExclusionStep(i) ==
    (QuorumHolds(i) /\ ~failOpen) => ~Acquires(i)

(***************************************************************************)
(* Every action other than BecomeLeader leaves `leader` alone, so the only  *)
(* way to acquire is through the guarded action.                           *)
(***************************************************************************)
LEMMA LeaderUnchangedElsewhere ==
    ASSUME NEW nb, NEW j, NEW v,
           \/ BoundedIntelligence(nb)
           \/ Campaign(j)
           \/ AppendEntry(j, v)
           \/ Commit(j)
    PROVE  leader' = leader
BY DEF BoundedIntelligence, Campaign, AppendEntry, Commit, vars

(***************************************************************************)
(* 0 is the "no leader" sentinel and Orderers = 1..N, so no orderer is 0.   *)
(***************************************************************************)
LEMMA OrdererNotZero == ASSUME NEW i \in Orderers PROVE i # 0
BY OrderersAssump

THEOREM Exclusion_PV_Thm ==
    ASSUME NEW i \in Orderers
    PROVE  Spec => [][ExclusionStep(i)]_vars
<1> USE OrderersAssump, FaultAssump
<1>1. [Next]_vars => [ExclusionStep(i)]_vars
  <2> SUFFICES ASSUME [Next]_vars, vars' # vars
               PROVE  ExclusionStep(i)
    OBVIOUS
  <2> SUFFICES ASSUME Next, QuorumHolds(i), ~failOpen
               PROVE  ~Acquires(i)
    BY DEF ExclusionStep
  <2>1. CASE \E nb \in [Orderers -> SUBSET Orderers] : BoundedIntelligence(nb)
    <3>1. leader' = leader
      BY <2>1 DEF BoundedIntelligence
    <3>2. QED
      BY <3>1, OrdererNotZero DEF Acquires
  <2>2. CASE \E j \in Orderers : Campaign(j)
    <3>1. leader' = leader
      BY <2>2 DEF Campaign, vars
    <3>2. QED
      BY <3>1, OrdererNotZero DEF Acquires
  <2>3. CASE \E j \in Orderers, v \in Values : AppendEntry(j, v)
    <3>1. leader' = leader
      BY <2>3 DEF AppendEntry
    <3>2. QED
      BY <3>1, OrdererNotZero DEF Acquires
  <2>4. CASE \E j \in Orderers : Commit(j)
    <3>1. leader' = leader
      BY <2>4 DEF Commit
    <3>2. QED
      BY <3>1, OrdererNotZero DEF Acquires
  <2>5. CASE \E j \in Orderers : BecomeLeader(j)
    <3>1. PICK j \in Orderers : BecomeLeader(j)
      BY <2>5
    (*********************************************************************)
    (* j = i is impossible: the vote-grant guard offers only failOpen or  *)
    (* "no quorum holds i", and the hypothesis denies both.              *)
    (*********************************************************************)
    <3>2. j # i
      <4>1. SUFFICES ASSUME j = i PROVE FALSE
        OBVIOUS
      <4>2. failOpen \/ ~QuorumHolds(i)
        BY <3>1, <4>1 DEF BecomeLeader, QuorumHolds
      <4>3. QED
        BY <4>2
    (*********************************************************************)
    (* With j # i, the only entry `leader` gains is j at currentTerm[j],  *)
    (* and every other entry keeps its old value, which is 0 on any term  *)
    (* that could witness acquisition.                                   *)
    (*********************************************************************)
    <3>3. leader' = [leader EXCEPT ![currentTerm[j]] = j]
      BY <3>1 DEF BecomeLeader
    <3>4. QED
      <4>1. SUFFICES ASSUME Acquires(i) PROVE FALSE
        OBVIOUS
      <4>2. PICK t \in 0..MaxTerm : leader[t] = 0 /\ leader'[t] = i
        BY <4>1 DEF Acquires
      <4>3. CASE t = currentTerm[j]
        BY <3>3, <4>2, <4>3, <3>2
      <4>4. CASE t # currentTerm[j]
        <5>1. leader'[t] = leader[t]
          BY <3>3, <4>4
        <5>2. QED
          BY <5>1, <4>2, OrdererNotZero
      <4>5. QED
        BY <4>3, <4>4
  <2>6. QED
    BY <2>1, <2>2, <2>3, <2>4, <2>5 DEF Next
<1>2. QED
  BY <1>1, PTL DEF Spec

=============================================================================
