---------------------------- MODULE BORA_pv_MC ----------------------------
(***************************************************************************)
(* A finite model check of the per-voter exclusion property, written so it  *)
(* can run under TLC where BORA_pv_excl cannot: that module EXTENDS TLAPS,  *)
(* which only ships with the prover.                                       *)
(*                                                                         *)
(* Why this module exists.  A Raft candidate votes for itself and that vote *)
(* passes no vote guard, so a quorum counted WITH the candidate models a    *)
(* guard stronger than the deployed one.  BORA_pv's BecomeLeader and        *)
(* BORA_pv_excl's QuorumHolds were corrected to quantify over               *)
(* SUBSET (Orderers \ {i}).  This module checks, on a small instance, that  *)
(* the corrected property actually holds of the corrected model, and that   *)
(* the OLD hypothesis does not -- so the correction is not cosmetic.        *)
(***************************************************************************)
EXTENDS BORA_pv, FiniteSets, Integers, Sequences

(* The corrected hypothesis: a quorum of voters OTHER than i holds i.       *)
QuorumOthers(i) ==
    \E Q \in SUBSET (Orderers \ {i}) : IsQuorum(Q) /\ \A j \in Q : i \in blacklist[j]

(* The hypothesis as it read before the correction: the quorum may contain  *)
(* the candidate itself.                                                    *)
QuorumAny(i) ==
    \E Q \in SUBSET Orderers : IsQuorum(Q) /\ \A j \in Q : i \in blacklist[j]

(* Acquisition as a step: a term that had no leader now has i.             *)
Acquires(i) ==
    \E t \in 0..MaxTerm : leader[t] = 0 /\ leader'[t] = i

(* What Proposition 7 claims, over the corrected model.                     *)
ExclusionOthers ==
    [][ \A i \in Orderers :
          (QuorumOthers(i) /\ ~failOpen) => ~Acquires(i) ]_vars

(* The same statement under the old hypothesis.  With BecomeLeader now      *)
(* gated on a quorum of others, this is the claim the paper used to make    *)
(* and it is expected to FAIL: a quorum {i, A} at N=3 leaves only A         *)
(* refusing, and i reaches a majority with its own vote and B's.            *)
ExclusionAny ==
    [][ \A i \in Orderers :
          (QuorumAny(i) /\ ~failOpen) => ~Acquires(i) ]_vars

(* Keep the search finite: logs and history are unbounded in the spec.      *)
MCConstraint ==
    /\ \A i \in Orderers : Len(log[i]) =< 1
    /\ Len(history) =< 1
    /\ blSeq =< 2
    /\ \A i \in Orderers : commitIndex[i] =< 1

=============================================================================
