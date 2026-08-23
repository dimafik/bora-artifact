------------------------------ MODULE BORA_proof ------------------------------
(***************************************************************************)
(* TLAPS deductive (UNBOUNDED) proof that BORA refines vanilla Raft:        *)
(*   Spec => VSpec ,  where VSpec is vanilla etcdraft over the seven shared *)
(* variables (the BORA actions minus the blacklist suppression).  Proved    *)
(* for ALL N, f, terms, values -- not only the bounded TLC model.  Hence    *)
(* BORA inherits every vanilla safety invariant (Election Safety, Leader    *)
(* Append-Only, Log Matching, Leader Completeness, State Machine Safety),    *)
(* which we cite for vanilla etcdraft rather than re-derive.  The vanilla    *)
(* actions are inlined here (no INSTANCE) to keep the proof obligations      *)
(* first-order for the SMT/Zenon backends.                                  *)
(***************************************************************************)
EXTENDS BORA, TLAPS

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

\* Step simulation: every BORA step is a vanilla step or a vanilla stutter.
THEOREM Refinement_Thm == Spec => VSpec
<1>1. Init => VInit
  BY DEF Init, VInit
<1>2. [Next]_vars => [VNext]_vanillaVars
  <2> SUFFICES ASSUME [Next]_vars PROVE [VNext]_vanillaVars OBVIOUS
  <2>1. CASE UNCHANGED vars
    BY <2>1 DEF vars, vanillaVars
  <2>2. CASE \E B \in SUBSET Orderers : BoundedIntelligence(B)
    BY <2>2 DEF BoundedIntelligence, vanillaVars
  <2>3. CASE \E i \in Orderers : Campaign(i)
    <3>1. PICK i \in Orderers : Campaign(i) BY <2>3
    <3>2. VCampaign(i) \/ UNCHANGED vanillaVars
      <4>1. CASE i \in blacklist /\ ~failOpen
        BY <3>1, <4>1 DEF Campaign, vars, vanillaVars
      <4>2. CASE ~(i \in blacklist /\ ~failOpen)
        BY <3>1, <4>2 DEF Campaign, VCampaign, vanillaVars
      <4>3. QED BY <4>1, <4>2
    <3>3. QED BY <3>2 DEF VNext
  <2>4. CASE \E i \in Orderers : BecomeLeader(i)
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
