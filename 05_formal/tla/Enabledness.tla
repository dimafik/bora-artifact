----------------------------- MODULE Enabledness -----------------------------
(***************************************************************************)
(* Model-checked support for the two enabledness facts used by Liveness.tla. *)
(*                                                                          *)
(*     ElectEnabled ==                                                      *)
(*         Inv /\ PendingCand => ENABLED <<ElectStep>>_vars                  *)
(*     CampEnabled ==                                                       *)
(*         Inv /\ ~HasLeader /\ ~PendingCand => ENABLED <<CampStep>>_vars    *)
(*                                                                          *)
(* Liveness.tla discharges both by ExpandENABLED (311/311, no axioms; see    *)
(* PROOF_RESULT.txt).  TLC evaluates ENABLED directly, so this module        *)
(* restates the two facts as state predicates and checks them over the same  *)
(* bounded model as an independent cross-check.                             *)
(*                                                                          *)
(* The bounded model is the one used elsewhere in the paper: N=5, F=2,       *)
(* MaxTerm=3.                                                               *)
(*                                                                          *)
(* Definitions below are copied VERBATIM from Liveness.tla.  This module     *)
(* deliberately does not EXTEND Liveness, because that module pulls in TLAPS *)
(* and SequenceTheorems, which are proof-only.  Vanilla.tla is the shared    *)
(* state machine, so the two developments check the same actions.            *)
(***************************************************************************)
EXTENDS Vanilla

\* ---- verbatim from Liveness.tla ----------------------------------------
HasLeader   == \E i \in Orderers : state[i] = "leader"
CampStep    == \E i \in Orderers : Campaign(i)
ElectStep   == \E i \in Orderers : BecomeLeader(i)
PendingCand == \E i \in Orderers : state[i] = "candidate" /\ leader[currentTerm[i]] = 0
LeaderInv   == \A t \in 0..MaxTerm : leader[t] # 0 => state[leader[t]] = "leader"
FollowerT0  == \A i \in Orderers : state[i] = "follower" => currentTerm[i] = 0
Inv         == TypeOK /\ LeaderInv /\ FollowerT0
\* ------------------------------------------------------------------------

\* Same shape as BORA.tla's StateConstraint (minus the blSeq bound, which has
\* no counterpart here): bound log growth so the model is finite.  With
\* Len(log[i]) <= 1 and commitIndex[i] <= 1 each orderer commits at most once,
\* so history is bounded too.
StateConstraint ==
    \A i \in Orderers :
        /\ Len(log[i]) <= 1
        /\ commitIndex[i] <= 1

(***************************************************************************)
(* THE TWO AXIOMS, AS TLC INVARIANTS.  Both must hold on every reachable    *)
(* state of the bounded model.                                             *)
(***************************************************************************)
ElectEnabledInv == (Inv /\ PendingCand)                => ENABLED <<ElectStep>>_vars
CampEnabledInv  == (Inv /\ ~HasLeader /\ ~PendingCand) => ENABLED <<CampStep>>_vars

(***************************************************************************)
(* NON-VACUITY PROBES.  An implication is cheap if its hypothesis is never  *)
(* satisfied.  Each predicate below must be VIOLATED by TLC; the reported   *)
(* counter-example is then a witness that the corresponding hypothesis is   *)
(* actually reachable.                                                     *)
(***************************************************************************)
Reach1 == ~(Inv /\ PendingCand)
Reach2 == ~(Inv /\ ~HasLeader /\ ~PendingCand)

(***************************************************************************)
(* MUTATION PROBES.  Each weakens one hypothesis and must be VIOLATED.      *)
(* A failure here shows the hypothesis is load-bearing rather than          *)
(* decoration, i.e. TLC is genuinely evaluating ENABLED and the axioms are  *)
(* not true for trivial reasons.                                           *)
(*                                                                         *)
(*   ElectEnabledMut drops "leader[currentTerm[i]] = 0" from PendingCand.   *)
(*   CampEnabledMut  drops "~PendingCand" from the campaign hypothesis.     *)
(***************************************************************************)
PendingCandWeak == \E i \in Orderers : state[i] = "candidate"
ElectEnabledMut == (Inv /\ PendingCandWeak) => ENABLED <<ElectStep>>_vars
CampEnabledMut  == (Inv /\ ~HasLeader)      => ENABLED <<CampStep>>_vars
=============================================================================
