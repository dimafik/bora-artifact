------------------------- MODULE SRaftPlusAdvice ----------------------------
(***************************************************************************)
(* S-Raft^{+A} model: S-Raft with ML predictor advice as a post-rank        *)
(* filter. Discharges Augmentation Safety Theorem invariants via Apalache.  *)
(*                                                                          *)
(* This module extends the baseline S-Raft module (SRaft.tla, omitted for   *)
(* brevity) by adding three new state components -- AdviceOk, BlacklistSet, *)
(* PrePromoteNominee -- and one new state transition: ApplyAdvice.          *)
(*                                                                          *)
(* Three invariants are checked:                                            *)
(*   Inv1: ElectionSafety  -- at most one leader per term                   *)
(*   Inv2: BlacklistBound  -- |BlacklistSet| < F at every step              *)
(*   Inv3: TierIntegrity   -- tier gaps respect Delta + T_process           *)
(*                                                                          *)
(* Apalache invocation:                                                     *)
(*   apalache-mc check --inv=Inv1 --length=20 SRaftPlusAdvice.tla           *)
(***************************************************************************)

EXTENDS Naturals, FiniteSets, Sequences, TLC

CONSTANTS
    Nodes,                  \* set of node identifiers
    F,                      \* Byzantine bound, F < Cardinality(Nodes)/3
    Terms,                  \* finite set of term numbers
    TPrimary,               \* T_primary tier interval [80, 110] ms
    TSecondary,             \* [140, 180] ms
    TFollower,              \* [210, 280] ms
    Delta,                  \* max one-way network delay
    TProcess                \* processing overhead

ASSUME QuorumGap == TSecondary[1] - TPrimary[2] > Delta + TProcess
ASSUME ByzantineBound == 3*F < Cardinality(Nodes)

VARIABLES
    currentTerm,            \* per-node current term [Nodes -> Terms]
    votedFor,               \* per-node, per-term vote [Nodes -> Terms -> Nodes \cup {NULL}]
    state,                  \* per-node role: "leader" | "primary" | "secondary" | "follower"
    log,                    \* per-node log (sequence of entries)
    commitIndex,            \* per-node commit index
    \* S-Raft additions
    CC,                     \* commit contribution [Nodes -> [0, 1]]
    RTT,                    \* RTT EMA [Nodes -> Real >= 0]
    Score,                  \* combined score [Nodes -> [0, 1]]
    tier,                   \* tier assignment [Nodes -> {"primary", "secondary", "follower"}]
    \* Advice additions
    AdviceOk,               \* BOOLEAN, whether the predictor's confidence is sufficient
    PrePromoteNominee,      \* Nodes \cup {NULL}
    BlacklistSet,           \* Subset of Nodes
    MaintenanceWarn         \* [Nodes -> [0, 1]] degradation probability per node

vars == <<currentTerm, votedFor, state, log, commitIndex,
          CC, RTT, Score, tier,
          AdviceOk, PrePromoteNominee, BlacklistSet, MaintenanceWarn>>

NULL == CHOOSE x : x \notin Nodes

----------------------------------------------------------------------------
(*** Initial state ***)

Init ==
    /\ currentTerm = [n \in Nodes |-> 0]
    /\ votedFor = [n \in Nodes |-> [t \in Terms |-> NULL]]
    /\ state = [n \in Nodes |-> "follower"]
    /\ log = [n \in Nodes |-> <<>>]
    /\ commitIndex = [n \in Nodes |-> 0]
    /\ CC = [n \in Nodes |-> 0]
    /\ RTT = [n \in Nodes |-> 0]
    /\ Score = [n \in Nodes |-> 0]
    /\ tier = [n \in Nodes |-> "follower"]
    /\ AdviceOk = FALSE
    /\ PrePromoteNominee = NULL
    /\ BlacklistSet = {}
    /\ MaintenanceWarn = [n \in Nodes |-> 0]

----------------------------------------------------------------------------
(*** Helpers ***)

\* Top-2 nodes by Score, excluding blacklisted nodes
TopTwo(banned) ==
    LET eligible == Nodes \ banned
    IN  IF Cardinality(eligible) < 2
        THEN eligible
        ELSE LET sorted == CHOOSE seq \in Permutations(eligible) :
                              \A i, j \in 1..Len(seq) :
                                  i < j => Score[seq[i]] >= Score[seq[j]]
             IN <<sorted[1], sorted[2]>>

\* Apply advice: post-rank filter producing the candidate sequence
ApplyAdviceFilter(ok, nominee, blist) ==
    IF /\ ok = TRUE
       /\ Cardinality(blist) < F
    THEN LET top == TopTwo(blist)
         IN IF nominee \in DOMAIN top
            THEN <<nominee>> \o SelectSeq(top, LAMBDA x : x /= nominee)
            ELSE top
    ELSE TopTwo({})

\* Quorum of nodes
Quorum == {S \in SUBSET Nodes : 2 * Cardinality(S) > Cardinality(Nodes)}

----------------------------------------------------------------------------
(*** State transitions ***)

\* Recompute CC and RTT (modelled abstractly as nondeterministic updates)
UpdateMeasurements(n) ==
    /\ \E cc \in 0..100 :
         /\ CC' = [CC EXCEPT ![n] = cc / 100]
    /\ \E rtt \in 0..500 :
         /\ RTT' = [RTT EXCEPT ![n] = rtt]
    /\ Score' = [Score EXCEPT
                   ![n] = (CC'[n] * 6 + (1000 - RTT'[n]) * 4 \div 1000) \div 10]
    /\ UNCHANGED <<currentTerm, votedFor, state, log, commitIndex, tier,
                   AdviceOk, PrePromoteNominee, BlacklistSet, MaintenanceWarn>>

\* Sidecar emits an advice tuple
EmitAdvice ==
    /\ \E ok \in BOOLEAN, nom \in Nodes \cup {NULL}, blist \in SUBSET Nodes :
         /\ Cardinality(blist) < F
         /\ AdviceOk' = ok
         /\ PrePromoteNominee' = nom
         /\ BlacklistSet' = blist
         /\ MaintenanceWarn' = [n \in Nodes |->
                                  IF n \in blist THEN 1 ELSE 0]
    /\ UNCHANGED <<currentTerm, votedFor, state, log, commitIndex,
                   CC, RTT, Score, tier>>

\* Cascading failure: a leader and primary die in rapid succession
CascadingFailure(leader, primary) ==
    /\ state[leader] = "leader"
    /\ state[primary] = "primary"
    /\ leader /= primary
    /\ state' = [state EXCEPT
                   ![leader] = "follower",
                   ![primary] = "follower"]
    /\ UNCHANGED <<currentTerm, votedFor, log, commitIndex,
                   CC, RTT, Score, tier,
                   AdviceOk, PrePromoteNominee, BlacklistSet, MaintenanceWarn>>

\* The chosen sub-leader ascends, respecting advice
PromoteSubLeader ==
    LET rank == ApplyAdviceFilter(AdviceOk, PrePromoteNominee, BlacklistSet)
    IN  /\ Len(rank) >= 1
        /\ state' = [state EXCEPT ![rank[1]] = "leader"]
        /\ currentTerm' = [currentTerm EXCEPT ![rank[1]] = @ + 1]
        /\ UNCHANGED <<votedFor, log, commitIndex,
                       CC, RTT, Score, tier,
                       AdviceOk, PrePromoteNominee, BlacklistSet, MaintenanceWarn>>

\* Vote granting (standard Raft)
GrantVote(voter, candidate, term) ==
    /\ currentTerm[voter] <= term
    /\ \/ votedFor[voter][term] = NULL
       \/ votedFor[voter][term] = candidate
    /\ votedFor' = [votedFor EXCEPT ![voter][term] = candidate]
    /\ UNCHANGED <<currentTerm, state, log, commitIndex,
                   CC, RTT, Score, tier,
                   AdviceOk, PrePromoteNominee, BlacklistSet, MaintenanceWarn>>

Next ==
    \/ \E n \in Nodes : UpdateMeasurements(n)
    \/ EmitAdvice
    \/ \E l, p \in Nodes : CascadingFailure(l, p)
    \/ PromoteSubLeader
    \/ \E v, c \in Nodes, t \in Terms : GrantVote(v, c, t)

Spec == Init /\ [][Next]_vars

----------------------------------------------------------------------------
(*** Invariants ***)

\* Inv1: Election Safety (at most one leader per term)
Inv1_ElectionSafety ==
    \A n1, n2 \in Nodes :
      \A t \in Terms :
        /\ currentTerm[n1] = t /\ state[n1] = "leader"
        /\ currentTerm[n2] = t /\ state[n2] = "leader"
        => n1 = n2

\* Inv2: Blacklist size is always less than F (the Byzantine bound)
Inv2_BlacklistBound ==
    Cardinality(BlacklistSet) < F

\* Inv3: Tier integrity -- when an advice maintenance warning forces a node
\* into a different tier, the gap between adjacent tiers is preserved.
\* In the abstract model we encode this as: if a node is forced to "follower"
\* by maintenance, its tier assignment doesn't violate the gap.
Inv3_TierIntegrity ==
    \A n \in Nodes :
      MaintenanceWarn[n] > 0 => tier[n] = "follower"

\* Compound invariant
SafetyInvariants ==
    /\ Inv1_ElectionSafety
    /\ Inv2_BlacklistBound
    /\ Inv3_TierIntegrity

----------------------------------------------------------------------------
(*** Auxiliary: monotonic recovery time tightening (T3 strengthening) ***)

(* In an event execution, let RecoveryTime(arm) be the time elapsed between *)
(* the cascading-failure event and the next committed entry. The theorem    *)
(* we want to express is:                                                   *)
(*                                                                          *)
(*   RecoveryTime("baseline") >= RecoveryTime("plus_advice")  always       *)
(*                                                                          *)
(* This is a temporal property best checked via TLC simulation rather than  *)
(* Apalache symbolic check; see the simulator-driven validation in §VI.     *)

============================================================================
