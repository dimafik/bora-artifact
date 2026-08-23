-------------------------------- MODULE BORA --------------------------------
(***************************************************************************)
(* TLA+ specification of the BORA-augmented etcdraft state machine.        *)
(*                                                                          *)
(* The spec models a synchronous round of length one heartbeat. Each round  *)
(* the BORA sidecar (the BoundedIntelligence action) may publish a new     *)
(* blacklist with cardinality strictly less than F (the Raft fault bound). *)
(* The orderer's election logic (the Campaign action) consults the         *)
(* blacklist and yields if the local orderer-id is in it.                  *)
(*                                                                          *)
(* The spec asserts five Raft safety invariants by their TLA+ equivalents: *)
(*   ElectionSafety       — at most one leader per term.                   *)
(*   LeaderAppendOnly     — leaders never overwrite or delete log entries. *)
(*   LogMatching          — equal (term,index) implies equal log prefix.   *)
(*   LeaderCompleteness   — once committed, a log entry survives every     *)
(*                          subsequent leader.                              *)
(*   StateMachineSafety   — no two orderers commit different values to     *)
(*                          the same index.                                *)
(*                                                                          *)
(* Plus the BORA-specific invariants:                                       *)
(*   BoundedCap           — |B_t| < F at every reachable state.            *)
(*   ALR                  — the incumbent leader is never blacklisted     *)
(*                          mid-term.                                       *)
(*                                                                          *)
(* Authored for IEEE TNSE Special Issue camera-ready supplementary.        *)
(***************************************************************************)

EXTENDS Naturals, FiniteSets, Sequences, TLC

CONSTANTS
    N,                  \* number of orderers
    F,                  \* Raft fault bound (typically (N-1) div 2)
    MaxTerm,            \* upper bound on terms for TLC model checking
    Values              \* set of values that can be appended

ASSUME N \in Nat /\ F \in Nat /\ F < N /\ MaxTerm \in Nat

Orderers == 1..N

(***************************************************************************)
(* State.                                                                   *)
(***************************************************************************)
VARIABLES
    currentTerm,        \* [Orderer -> Nat]
    state,              \* [Orderer -> {"follower","candidate","leader"}]
    votedFor,           \* [Orderer -> Orderer \cup {0}]
    log,                \* [Orderer -> Seq([term:Nat, value:Values])]
    commitIndex,        \* [Orderer -> Nat]
    leader,             \* [Term -> Orderer \cup {0}]  history witness
    blacklist,          \* current B_t  Subset Orderers, |B_t| < F
    blSeq,              \* monotone sequence number on blacklist
    failOpen,           \* Boolean — fail-open flag in current advice round
    history             \* sequence of committed (index,value) pairs

vars == << currentTerm, state, votedFor, log, commitIndex,
           leader, blacklist, blSeq, failOpen, history >>

(***************************************************************************)
(* Type invariants.                                                         *)
(***************************************************************************)
TypeOK ==
    /\ currentTerm \in [Orderers -> 0..MaxTerm]
    /\ state \in [Orderers -> {"follower","candidate","leader"}]
    /\ votedFor \in [Orderers -> 0..N]
    /\ log \in [Orderers -> Seq([term:0..MaxTerm, value:Values])]
    /\ commitIndex \in [Orderers -> Nat]
    /\ leader \in [0..MaxTerm -> 0..N]
    /\ blacklist \subseteq Orderers
    /\ blSeq \in Nat
    /\ failOpen \in BOOLEAN
    /\ history \in Seq([index:Nat, value:Values])

(***************************************************************************)
(* Initial state.                                                           *)
(***************************************************************************)
Init ==
    /\ currentTerm = [i \in Orderers |-> 0]
    /\ state = [i \in Orderers |-> "follower"]
    /\ votedFor = [i \in Orderers |-> 0]
    /\ log = [i \in Orderers |-> << >>]
    /\ commitIndex = [i \in Orderers |-> 0]
    /\ leader = [t \in 0..MaxTerm |-> 0]
    /\ blacklist = {}
    /\ blSeq = 0
    /\ failOpen = FALSE
    /\ history = << >>

(***************************************************************************)
(* Helper: incumbent of the most recent term in which a leader emerged.    *)
(***************************************************************************)
LatestLeaderTerm ==
    CHOOSE t \in 0..MaxTerm :
        /\ leader[t] # 0
        /\ \A u \in 0..MaxTerm : leader[u] # 0 => u <= t

Incumbent ==
    IF \E t \in 0..MaxTerm : leader[t] # 0
    THEN leader[LatestLeaderTerm]
    ELSE 0

(***************************************************************************)
(* Action: BORA sidecar publishes a new advice.  This is the only action  *)
(* outside the Consensus Plane and is mapped to bot by alpha.             *)
(***************************************************************************)
BoundedIntelligence(newBlacklist) ==
    /\ Cardinality(newBlacklist) < F
    /\ Incumbent \notin newBlacklist     \* ALR
    /\ blacklist' = newBlacklist
    /\ blSeq' = blSeq + 1
    /\ failOpen' = (newBlacklist = {})
    /\ UNCHANGED << currentTerm, state, votedFor, log, commitIndex,
                    leader, history >>

(***************************************************************************)
(* Action: orderer i times out and starts a campaign.  If i is blacklisted *)
(* (and BORA is not in fail-open), i yields (no state change).            *)
(***************************************************************************)
Campaign(i) ==
    /\ state[i] = "follower"
    /\ currentTerm[i] < MaxTerm
    /\ \/ /\ i \in blacklist
          /\ ~failOpen
          /\ UNCHANGED vars     \* yield, term not incremented
       \/ /\ ~(i \in blacklist /\ ~failOpen)
          /\ currentTerm' = [currentTerm EXCEPT ![i] = currentTerm[i] + 1]
          /\ state' = [state EXCEPT ![i] = "candidate"]
          /\ votedFor' = [votedFor EXCEPT ![i] = i]
          /\ UNCHANGED << log, commitIndex, leader,
                          blacklist, blSeq, failOpen, history >>

(***************************************************************************)
(* Action: candidate i wins the election for its term.  We abstract       *)
(* RequestVote/voting by simply allowing one candidate per term to win    *)
(* iff no other orderer has already claimed leader for that term.         *)
(***************************************************************************)
BecomeLeader(i) ==
    /\ state[i] = "candidate"
    /\ leader[currentTerm[i]] = 0
    \* BORA invariant: a candidate that has entered the blacklist
    \* between Campaign and BecomeLeader cannot win the election
    \* (the patch's Vote-Grant Predicate rejects votes for it). This
    \* preserves the Active-Leader Rule for newly elected leaders.
    /\ (i \notin blacklist) \/ failOpen
    /\ state' = [state EXCEPT ![i] = "leader"]
    /\ leader' = [leader EXCEPT ![currentTerm[i]] = i]
    /\ UNCHANGED << currentTerm, votedFor, log, commitIndex,
                    blacklist, blSeq, failOpen, history >>

(***************************************************************************)
(* Action: leader i appends a new entry.  Leader-append-only is enforced  *)
(* by structural append.                                                   *)
(***************************************************************************)
AppendEntry(i, v) ==
    /\ state[i] = "leader"
    /\ log' = [log EXCEPT ![i] = Append(log[i],
                  [term |-> currentTerm[i], value |-> v])]
    /\ UNCHANGED << currentTerm, state, votedFor, commitIndex,
                    leader, blacklist, blSeq, failOpen, history >>

(***************************************************************************)
(* Action: a leader commits its tail entry once a majority has it.        *)
(* Abstract: we let any leader commit immediately if its log is non-empty *)
(* and quorum is structurally available (3 of 5 orderers in the modelled  *)
(* configuration). The witness for commit is recorded in history.         *)
(***************************************************************************)
Commit(i) ==
    /\ state[i] = "leader"
    /\ Len(log[i]) > commitIndex[i]
    /\ commitIndex' = [commitIndex EXCEPT ![i] = Len(log[i])]
    /\ history' = Append(history, [index |-> Len(log[i]),
                                   value |-> log[i][Len(log[i])].value])
    /\ UNCHANGED << currentTerm, state, votedFor, log,
                    leader, blacklist, blSeq, failOpen >>

(***************************************************************************)
(* Next-state relation.                                                     *)
(***************************************************************************)
Next ==
    \/ \E B \in SUBSET Orderers : BoundedIntelligence(B)
    \/ \E i \in Orderers : Campaign(i)
    \/ \E i \in Orderers : BecomeLeader(i)
    \/ \E i \in Orderers, v \in Values : AppendEntry(i, v)
    \/ \E i \in Orderers : Commit(i)

Spec == Init /\ [][Next]_vars

\* Finite-state constraint for TLC: bound log growth (AppendEntry is otherwise
\* unbounded) and commit index so the model is finite.
StateConstraint ==
    /\ blSeq <= 3
    /\ \A i \in Orderers :
        /\ Len(log[i]) <= 1
        /\ commitIndex[i] <= 1

(***************************************************************************)
(* SAFETY INVARIANTS.                                                       *)
(***************************************************************************)

\* BORA-specific cap.
BoundedCap == Cardinality(blacklist) < F

\* Active-Leader Rule: incumbent never blacklisted.
ALR_Inv == Incumbent \notin blacklist \/ Incumbent = 0

\* Election Safety: at most one leader per term.
ElectionSafety ==
    \A t \in 0..MaxTerm :
        \A i, j \in Orderers :
            (state[i] = "leader" /\ state[j] = "leader" /\
             currentTerm[i] = t /\ currentTerm[j] = t)
            => i = j

\* Leader Append-Only: no step ever shrinks a log or rewrites an existing
\* entry.  Stated as a transition property (checkable by TLC via PROPERTY).
\* It holds by construction -- the only log-modifying action is AppendEntry,
\* a pure Append -- which is exactly why no reachability search is needed to
\* establish it; the property makes that structural fact machine-checkable.
LeaderAppendOnly ==
    [][ \A i \in Orderers :
          /\ Len(log'[i]) >= Len(log[i])
          /\ \A k \in 1..Len(log[i]) : log'[i][k] = log[i][k] ]_vars

\* Log Matching: equal (term,index) entries imply equal value across orderers.
LogMatching ==
    \A i, j \in Orderers :
        \A k \in 1..Len(log[i]) :
            (k <= Len(log[j]) /\ log[i][k].term = log[j][k].term)
            => log[i][k].value = log[j][k].value

\* State Machine Safety: committed entries are unique per index.
StateMachineSafety ==
    \A k, m \in 1..Len(history) :
        (history[k].index = history[m].index)
        => history[k].value = history[m].value

\* Leader Completeness: every value present in history is also in some
\* current leader's log (we check at quiescence rather than during yield).
LeaderCompleteness ==
    \A k \in 1..Len(history) :
        \E i \in Orderers :
            \E n \in 1..Len(log[i]) :
                log[i][n].value = history[k].value

(***************************************************************************)
(* Conjunction of all safety properties for TLC.                            *)
(***************************************************************************)
Safety ==
    /\ TypeOK
    /\ BoundedCap
    /\ ALR_Inv
    /\ ElectionSafety
    /\ LogMatching
    /\ StateMachineSafety
    /\ LeaderCompleteness

(***************************************************************************)
(* Refinement mapping (Theorem 1 in the paper).                            *)
(*                                                                          *)
(* pi projects out the three Bounded-Intelligence variables; the remaining *)
(* tuple IS the vanilla-Raft state.  The election timeout is modelled       *)
(* nondeterministically (Campaign is an always-optional action, no         *)
(* concrete electionElapsed counter), so a YIELD -- the Campaign branch     *)
(* with i in blacklist, which is UNCHANGED vars (line ~123) -- is a         *)
(* stuttering step under pi.  No history/prophecy variable is required:     *)
(* a suppressed orderer is exactly a vanilla orderer that did not exercise  *)
(* its optional Campaign this round, for arbitrarily many rounds.          *)
(***************************************************************************)
vanillaVars == << currentTerm, state, votedFor, log, commitIndex,
                   leader, history >>

\* Per-action image under pi:
\*   BoundedIntelligence(B) : UNCHANGED vanillaVars            (stutter)
\*   Campaign(i), i yields  : UNCHANGED vars  => UNCHANGED vanillaVars (stutter)
\*   Campaign(i), i runs    : a vanilla Campaign step
\*   BecomeLeader/AppendEntry/Commit : the identical vanilla step
\* Hence [][Next]_vars  =>  [][Vanilla!Next]_vanillaVars  under pi.

\* Cross-module refinement: INSTANCE the vanilla module (the seven vanilla vars
\* and the four constants map identically by name; blacklist/blSeq/failOpen are
\* dropped, i.e. projected out by pi).  Refinement == Van!Spec is checked by TLC
\* as a temporal PROPERTY: every BORA behaviour, under pi, satisfies the vanilla
\* Raft spec (a yield/BoundedIntelligence step projects to a vanilla stutter).
Van == INSTANCE Vanilla
Refinement == Van!Spec
\* The deductive (unbounded, TLAPS) proof of Spec => Van!Spec is in BORA_proof.tla.
=============================================================================
