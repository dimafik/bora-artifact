------------------------------- MODULE Vanilla -------------------------------
(***************************************************************************)
(* Vanilla etcdraft state machine: the SAME model as BORA.tla minus the     *)
(* three Bounded-Intelligence variables and the blacklist suppression.      *)
(* BORA.tla INSTANCEs this module and TLC checks Spec => Vanilla!Spec, i.e.  *)
(* every BORA behaviour, projected by pi (dropping blacklist/blSeq/failOpen),*)
(* is a vanilla-Raft behaviour. This mechanises the trace refinement of      *)
(* Theorem 1 directly, not merely via the per-step invariants.              *)
(***************************************************************************)
EXTENDS Naturals, FiniteSets, Sequences, TLC

CONSTANTS N, F, MaxTerm, Values
ASSUME N \in Nat /\ F \in Nat /\ F < N /\ MaxTerm \in Nat
Orderers == 1..N

VARIABLES currentTerm, state, votedFor, log, commitIndex, leader, history
vars == << currentTerm, state, votedFor, log, commitIndex, leader, history >>

TypeOK ==
    /\ currentTerm \in [Orderers -> 0..MaxTerm]
    /\ state \in [Orderers -> {"follower","candidate","leader"}]
    /\ votedFor \in [Orderers -> 0..N]
    /\ log \in [Orderers -> Seq([term:0..MaxTerm, value:Values])]
    /\ commitIndex \in [Orderers -> Nat]
    /\ leader \in [0..MaxTerm -> 0..N]
    /\ history \in Seq([index:Nat, value:Values])

Init ==
    /\ currentTerm = [i \in Orderers |-> 0]
    /\ state = [i \in Orderers |-> "follower"]
    /\ votedFor = [i \in Orderers |-> 0]
    /\ log = [i \in Orderers |-> << >>]
    /\ commitIndex = [i \in Orderers |-> 0]
    /\ leader = [t \in 0..MaxTerm |-> 0]
    /\ history = << >>

\* Vanilla election timeout: always-optional Campaign (no blacklist gate).
Campaign(i) ==
    /\ state[i] = "follower"
    /\ currentTerm[i] < MaxTerm
    /\ currentTerm' = [currentTerm EXCEPT ![i] = currentTerm[i] + 1]
    /\ state' = [state EXCEPT ![i] = "candidate"]
    /\ votedFor' = [votedFor EXCEPT ![i] = i]
    /\ UNCHANGED << log, commitIndex, leader, history >>

\* Vanilla leader win: no blacklist precondition.
BecomeLeader(i) ==
    /\ state[i] = "candidate"
    /\ leader[currentTerm[i]] = 0
    /\ state' = [state EXCEPT ![i] = "leader"]
    /\ leader' = [leader EXCEPT ![currentTerm[i]] = i]
    /\ UNCHANGED << currentTerm, votedFor, log, commitIndex, history >>

AppendEntry(i, v) ==
    /\ state[i] = "leader"
    /\ log' = [log EXCEPT ![i] = Append(log[i], [term |-> currentTerm[i], value |-> v])]
    /\ UNCHANGED << currentTerm, state, votedFor, commitIndex, leader, history >>

Commit(i) ==
    /\ state[i] = "leader"
    /\ Len(log[i]) > commitIndex[i]
    /\ commitIndex' = [commitIndex EXCEPT ![i] = Len(log[i])]
    /\ history' = Append(history, [index |-> Len(log[i]), value |-> log[i][Len(log[i])].value])
    /\ UNCHANGED << currentTerm, state, votedFor, log, leader >>

Next ==
    \/ \E i \in Orderers : Campaign(i)
    \/ \E i \in Orderers : BecomeLeader(i)
    \/ \E i \in Orderers, v \in Values : AppendEntry(i, v)
    \/ \E i \in Orderers : Commit(i)

Spec == Init /\ [][Next]_vars
=============================================================================
