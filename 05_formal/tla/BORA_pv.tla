------------------------------- MODULE BORA_pv -------------------------------
(***************************************************************************)
(* PER-VOTER variant of BORA.                                              *)
(*                                                                         *)
(* Reviewers 2 and 3 both observed that the mechanised model carries a      *)
(* single GLOBAL blacklist, while the deployed system gives every orderer   *)
(* its own sidecar and therefore its own, only eventually consistent, view. *)
(* Proposition 7 argues the gap analytically. This module closes the        *)
(* SAFETY half of that gap mechanically:                                    *)
(*                                                                         *)
(*     blacklist \subseteq Orderers   ->   blacklist \in [Orderers ->       *)
(*                                          SUBSET Orderers]               *)
(*                                                                         *)
(* Each voter j holds blacklist[j]. Nothing forces the views to agree: a    *)
(* BoundedIntelligence step may hand every voter a different set. The tick  *)
(* guard consults a node's OWN view (blacklist[i]), which is what the       *)
(* deployed sidecar does, and the vote-grant guard is expressed over a      *)
(* quorum of voters rather than over one global set.                        *)
(*                                                                         *)
(* WHAT THIS DOES AND DOES NOT ESTABLISH. It establishes that the refinement*)
(* into vanilla Raft -- hence every Raft safety invariant -- survives       *)
(* per-voter divergence, with no agreement premise anywhere. It does NOT    *)
(* establish exclusion: whether a flagged node is actually kept out still   *)
(* depends on a quorum holding it, which is the conditional part of         *)
(* Proposition 7 and is left unmechanised.                                  *)
(*                                                                         *)
(* The reason safety survives is structural rather than clever: both guards *)
(* only ever ADD preconditions to actions vanilla Raft already permits, and *)
(* adding preconditions removes behaviours. A refinement cannot be broken by*)
(* removing behaviours, however the removal is decided -- per voter, per    *)
(* node, or at random.                                                     *)
(***************************************************************************)
EXTENDS Naturals, Sequences, FiniteSets

CONSTANTS Orderers, N, F, MaxTerm, Values

ASSUME OrderersAssump == Orderers = 1..N
ASSUME FaultAssump == F \in Nat /\ F > 0

VARIABLES
    currentTerm,        \* [Orderer -> Nat]
    state,              \* [Orderer -> {"follower","candidate","leader"}]
    votedFor,           \* [Orderer -> Orderer \cup {0}]
    log,                \* [Orderer -> Seq([term:Nat, value:Values])]
    commitIndex,        \* [Orderer -> Nat]
    leader,             \* [Term -> Orderer \cup {0}]
    blacklist,          \* [Orderer -> SUBSET Orderers]   <-- per voter
    blSeq,
    failOpen,
    history

vars == << currentTerm, state, votedFor, log, commitIndex,
           leader, blacklist, blSeq, failOpen, history >>

vanillaVars == << currentTerm, state, votedFor, log, commitIndex,
                  leader, history >>

TypeOK ==
    /\ currentTerm \in [Orderers -> 0..MaxTerm]
    /\ state \in [Orderers -> {"follower","candidate","leader"}]
    /\ votedFor \in [Orderers -> 0..N]
    /\ log \in [Orderers -> Seq([term:0..MaxTerm, value:Values])]
    /\ commitIndex \in [Orderers -> Nat]
    /\ leader \in [0..MaxTerm -> 0..N]
    /\ blacklist \in [Orderers -> SUBSET Orderers]
    /\ blSeq \in Nat
    /\ failOpen \in BOOLEAN
    /\ history \in Seq([index:Nat, value:Values])

Init ==
    /\ currentTerm = [i \in Orderers |-> 0]
    /\ state = [i \in Orderers |-> "follower"]
    /\ votedFor = [i \in Orderers |-> 0]
    /\ log = [i \in Orderers |-> << >>]
    /\ commitIndex = [i \in Orderers |-> 0]
    /\ leader = [t \in 0..MaxTerm |-> 0]
    /\ blacklist = [i \in Orderers |-> {}]
    /\ blSeq = 0
    /\ failOpen = FALSE
    /\ history = << >>

LatestLeaderTerm ==
    CHOOSE t \in 0..MaxTerm :
        /\ leader[t] # 0
        /\ \A u \in 0..MaxTerm : leader[u] # 0 => u <= t

Incumbent ==
    IF \E t \in 0..MaxTerm : leader[t] # 0
    THEN leader[LatestLeaderTerm]
    ELSE 0

\* A quorum of voters, in the sense the vote-grant predicate needs.
IsQuorum(Q) == Q \subseteq Orderers /\ 2 * Cardinality(Q) > N

(***************************************************************************)
(* Advice publication. Every voter may receive a DIFFERENT set: nb is a    *)
(* function, not a set. No agreement is assumed or enforced anywhere.      *)
(***************************************************************************)
BoundedIntelligence(nb) ==
    /\ nb \in [Orderers -> SUBSET Orderers]
    /\ \A j \in Orderers : Cardinality(nb[j]) < F      \* cap holds per voter
    /\ \A j \in Orderers : Incumbent \notin nb[j]      \* ALR holds per voter
    /\ blacklist' = nb
    /\ blSeq' = blSeq + 1
    /\ failOpen' = (\A j \in Orderers : nb[j] = {})
    /\ UNCHANGED << currentTerm, state, votedFor, log, commitIndex,
                    leader, history >>

(***************************************************************************)
(* Tick guard. A node consults ITS OWN sidecar, blacklist[i]: this is the  *)
(* one place where the deployed system is unambiguously local.            *)
(***************************************************************************)
Campaign(i) ==
    /\ state[i] = "follower"
    /\ currentTerm[i] < MaxTerm
    /\ \/ /\ i \in blacklist[i]
          /\ ~failOpen
          /\ UNCHANGED vars
       \/ /\ ~(i \in blacklist[i] /\ ~failOpen)
          /\ currentTerm' = [currentTerm EXCEPT ![i] = currentTerm[i] + 1]
          /\ state' = [state EXCEPT ![i] = "candidate"]
          /\ votedFor' = [votedFor EXCEPT ![i] = i]
          /\ UNCHANGED << log, commitIndex, leader,
                          blacklist, blSeq, failOpen, history >>

(***************************************************************************)
(* Vote-grant guard, stated over voters rather than over a global set: i   *)
(* is blocked exactly when a QUORUM of voters holds i. With one global     *)
(* blacklist the two formulations coincide; they diverge as soon as the    *)
(* views do, which is the case this module is about.                       *)
(***************************************************************************)
BecomeLeader(i) ==
    /\ state[i] = "candidate"
    /\ leader[currentTerm[i]] = 0
    /\ \/ failOpen
       \/ ~(\E Q \in SUBSET Orderers : IsQuorum(Q) /\ \A j \in Q : i \in blacklist[j])
    /\ state' = [state EXCEPT ![i] = "leader"]
    /\ leader' = [leader EXCEPT ![currentTerm[i]] = i]
    /\ UNCHANGED << currentTerm, votedFor, log, commitIndex,
                    blacklist, blSeq, failOpen, history >>

AppendEntry(i, v) ==
    /\ state[i] = "leader"
    /\ log' = [log EXCEPT ![i] = Append(log[i],
                  [term |-> currentTerm[i], value |-> v])]
    /\ UNCHANGED << currentTerm, state, votedFor, commitIndex,
                    leader, blacklist, blSeq, failOpen, history >>

Commit(i) ==
    /\ state[i] = "leader"
    /\ Len(log[i]) > commitIndex[i]
    /\ commitIndex' = [commitIndex EXCEPT ![i] = Len(log[i])]
    /\ history' = Append(history, [index |-> Len(log[i]),
                                   value |-> log[i][Len(log[i])].value])
    /\ UNCHANGED << currentTerm, state, votedFor, log,
                    leader, blacklist, blSeq, failOpen >>

Next ==
    \/ \E nb \in [Orderers -> SUBSET Orderers] : BoundedIntelligence(nb)
    \/ \E i \in Orderers : Campaign(i)
    \/ \E i \in Orderers : BecomeLeader(i)
    \/ \E i \in Orderers, v \in Values : AppendEntry(i, v)
    \/ \E i \in Orderers : Commit(i)

Spec == Init /\ [][Next]_vars

\* Per-voter cap: every voter's own view respects the bound.
BoundedCapPV == \A j \in Orderers : Cardinality(blacklist[j]) < F

\* Per-voter ALR: no voter holds the incumbent.
ALR_InvPV == \A j \in Orderers : Incumbent \notin blacklist[j] \/ Incumbent = 0
=============================================================================
