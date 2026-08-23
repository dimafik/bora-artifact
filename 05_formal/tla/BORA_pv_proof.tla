---------------------------- MODULE BORA_pv_proof ----------------------------
(***************************************************************************)
(* TLAPS proof that the PER-VOTER BORA refines vanilla Raft:               *)
(*     Spec => VSpec                                                       *)
(*                                                                         *)
(* Same claim as BORA_proof.tla, but over a blacklist that is a FUNCTION   *)
(* from voters to sets rather than one global set. No premise anywhere     *)
(* says the voters agree; BoundedIntelligence may hand each voter a        *)
(* different set on every step.                                            *)
(*                                                                         *)
(* The proof is nearly the same shape as the global one, and that is the   *)
(* point. Both BORA guards only ADD preconditions to actions vanilla Raft  *)
(* already permits:                                                        *)
(*                                                                         *)
(*   - Campaign's yield branch leaves every variable unchanged, which is a *)
(*     vanilla stutter regardless of whose view caused the yield.          *)
(*   - BecomeLeader's quorum guard is an extra conjunct on an action whose *)
(*     remaining conjuncts are exactly VBecomeLeader's.                    *)
(*                                                                         *)
(* Adding preconditions removes behaviours, and removing behaviours cannot *)
(* break a refinement. So safety transfers UNCONDITIONALLY -- it never     *)
(* needed the voters to agree. Exclusion is the part that does need        *)
(* agreement, and it is not claimed here.                                  *)
(***************************************************************************)
EXTENDS BORA_pv, TLAPS

\* Vanilla etcdraft over the seven shared variables (no blacklist gate).
VInit ==
    /\ currentTerm = [i \in Orderers |-> 0]
    /\ state = [i \in Orderers |-> "follower"]
    /\ votedFor = [i \in Orderers |-> 0]
    /\ log = [i \in Orderers |-> << >>]
    /\ commitIndex = [i \in Orderers |-> 0]
    /\ leader = [t \in 0..MaxTerm |-> 0]
    /\ history = << >>

VCampaign(i) ==
    /\ state[i] = "follower" /\ currentTerm[i] < MaxTerm
    /\ currentTerm' = [currentTerm EXCEPT ![i] = currentTerm[i] + 1]
    /\ state' = [state EXCEPT ![i] = "candidate"]
    /\ votedFor' = [votedFor EXCEPT ![i] = i]
    /\ UNCHANGED << log, commitIndex, leader, history >>

VBecomeLeader(i) ==
    /\ state[i] = "candidate" /\ leader[currentTerm[i]] = 0
    /\ state' = [state EXCEPT ![i] = "leader"]
    /\ leader' = [leader EXCEPT ![currentTerm[i]] = i]
    /\ UNCHANGED << currentTerm, votedFor, log, commitIndex, history >>

VAppendEntry(i, v) ==
    /\ state[i] = "leader"
    /\ log' = [log EXCEPT ![i] = Append(log[i], [term |-> currentTerm[i], value |-> v])]
    /\ UNCHANGED << currentTerm, state, votedFor, commitIndex, leader, history >>

VCommit(i) ==
    /\ state[i] = "leader" /\ Len(log[i]) > commitIndex[i]
    /\ commitIndex' = [commitIndex EXCEPT ![i] = Len(log[i])]
    /\ history' = Append(history, [index |-> Len(log[i]), value |-> log[i][Len(log[i])].value])
    /\ UNCHANGED << currentTerm, state, votedFor, log, leader >>

VNext ==
    \/ \E i \in Orderers : VCampaign(i)
    \/ \E i \in Orderers : VBecomeLeader(i)
    \/ \E i \in Orderers, v \in Values : VAppendEntry(i, v)
    \/ \E i \in Orderers : VCommit(i)

VSpec == VInit /\ [][VNext]_vanillaVars

THEOREM Refinement_PV_Thm == Spec => VSpec
<1>1. Init => VInit
  BY DEF Init, VInit
<1>2. [Next]_vars => [VNext]_vanillaVars
  <2> SUFFICES ASSUME [Next]_vars PROVE [VNext]_vanillaVars OBVIOUS
  <2>1. CASE UNCHANGED vars
    BY <2>1 DEF vars, vanillaVars
  <2>2. CASE \E nb \in [Orderers -> SUBSET Orderers] : BoundedIntelligence(nb)
    BY <2>2 DEF BoundedIntelligence, vanillaVars
  <2>3. CASE \E i \in Orderers : Campaign(i)
    <3>1. PICK i \in Orderers : Campaign(i) BY <2>3
    <3>2. VCampaign(i) \/ UNCHANGED vanillaVars
      \* The yield branch is a stutter whoever's view triggered it.
      <4>1. CASE i \in blacklist[i] /\ ~failOpen
        BY <3>1, <4>1 DEF Campaign, vars, vanillaVars
      <4>2. CASE ~(i \in blacklist[i] /\ ~failOpen)
        BY <3>1, <4>2 DEF Campaign, VCampaign, vanillaVars
      <4>3. QED BY <4>1, <4>2
    <3>3. QED BY <3>2 DEF VNext
  <2>4. CASE \E i \in Orderers : BecomeLeader(i)
    \* The quorum guard is an extra conjunct; the rest is VBecomeLeader verbatim.
    <3>1. PICK i \in Orderers : BecomeLeader(i) BY <2>4
    <3>2. VBecomeLeader(i) BY <3>1 DEF BecomeLeader, VBecomeLeader
    <3>3. QED BY <3>2 DEF VNext
  <2>5. CASE \E i \in Orderers, v \in Values : AppendEntry(i, v)
    <3>1. PICK i \in Orderers, v \in Values : AppendEntry(i, v) BY <2>5
    <3>2. VAppendEntry(i, v) BY <3>1 DEF AppendEntry, VAppendEntry
    <3>3. QED BY <3>2 DEF VNext
  <2>6. CASE \E i \in Orderers : Commit(i)
    <3>1. PICK i \in Orderers : Commit(i) BY <2>6
    <3>2. VCommit(i) BY <3>1 DEF Commit, VCommit
    <3>3. QED BY <3>2 DEF VNext
  <2>7. QED BY <2>1, <2>2, <2>3, <2>4, <2>5, <2>6 DEF Next
<1>3. QED BY <1>1, <1>2, PTL DEF Spec, VSpec
=============================================================================
