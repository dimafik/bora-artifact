--------------------------- MODULE EnBisect ---------------------------
(***************************************************************************)
(* Why does ENABLED lift over the existential for BecomeLeader but not for  *)
(* Campaign?  Context clutter and mixed arithmetic were both ruled out      *)
(* (EnCamp.tla V1-V4 all fail at the same obligation, and the inner         *)
(* ENABLED <<Campaign(k)>>_vars succeeds).                                  *)
(*                                                                         *)
(* So bisect the ACTION.  Same proof text in every case, only the action    *)
(* changes.  Campaign differs from BecomeLeader in exactly three ways:      *)
(*                                                                         *)
(*   (a) an arithmetic GUARD          currentTerm[i] < MaxTerm              *)
(*   (b) an arithmetic ASSIGNMENT     currentTerm' = [... ! [i] = ...+1]    *)
(*   (c) three assignments, not two                                        *)
(*                                                                         *)
(* B0 is the control: BecomeLeader, known to work.                         *)
(***************************************************************************)
EXTENDS Vanilla, TLAPS

ASSUME NAssume  == N \in Nat /\ N >= 1
ASSUME MTAssume == MaxTerm \in Nat /\ MaxTerm >= 1

\* ---- control: the action whose lift is known to succeed ------------------
ElectStep == \E i \in Orderers : BecomeLeader(i)

\* ---- (a) removed: no arithmetic guard ------------------------------------
CampNoGuard(i) ==
    /\ state[i] = "follower"
    /\ currentTerm' = [currentTerm EXCEPT ![i] = currentTerm[i] + 1]
    /\ state' = [state EXCEPT ![i] = "candidate"]
    /\ votedFor' = [votedFor EXCEPT ![i] = i]
    /\ UNCHANGED << log, commitIndex, leader, history >>
StepNoGuard == \E i \in Orderers : CampNoGuard(i)

\* ---- (b) removed: no arithmetic assignment -------------------------------
CampNoArith(i) ==
    /\ state[i] = "follower"
    /\ currentTerm[i] < MaxTerm
    /\ state' = [state EXCEPT ![i] = "candidate"]
    /\ votedFor' = [votedFor EXCEPT ![i] = i]
    /\ UNCHANGED << currentTerm, log, commitIndex, leader, history >>
StepNoArith == \E i \in Orderers : CampNoArith(i)

\* ---- (c) reduced to two assignments, keeping both arithmetic features ----
CampTwo(i) ==
    /\ state[i] = "follower"
    /\ currentTerm[i] < MaxTerm
    /\ currentTerm' = [currentTerm EXCEPT ![i] = currentTerm[i] + 1]
    /\ state' = [state EXCEPT ![i] = "candidate"]
    /\ UNCHANGED << votedFor, log, commitIndex, leader, history >>
StepTwo == \E i \in Orderers : CampTwo(i)

\* ---- full Campaign, for reference ----------------------------------------
CampStep == \E i \in Orderers : Campaign(i)

\* FULL TypeOK, not a partial typing.  The witness for ENABLED must construct
\* primed values for every variable the action assigns: BecomeLeader builds
\* [leader EXCEPT ![currentTerm[i]] = i] and Campaign builds
\* [votedFor EXCEPT ![i] = i], so the backend needs those two domains as well.
\* Liveness.tla's ElectEnabled had Inv (hence TypeOK) in scope and therefore had
\* them; the earlier attempts here supplied only state and currentTerm.
Typed == TypeOK

(***************************************************************************)
(* B0  control -- BecomeLeader.  Expected: PROVED.                         *)
(***************************************************************************)
THEOREM B0 == ASSUME NEW k \in Orderers
              PROVE  (Typed /\ state[k] = "candidate" /\ leader[currentTerm[k]] = 0)
                     => ENABLED <<ElectStep>>_vars
  BY ExpandENABLED DEF Typed, TypeOK, ElectStep, BecomeLeader, vars

(***************************************************************************)
(* B1  (a) removed -- arithmetic guard gone, arithmetic assignment kept.   *)
(***************************************************************************)
THEOREM B1 == ASSUME NEW k \in Orderers
              PROVE  (Typed /\ state[k] = "follower")
                     => ENABLED <<StepNoGuard>>_vars
  BY ExpandENABLED DEF Typed, TypeOK, StepNoGuard, CampNoGuard, vars

(***************************************************************************)
(* B2  (b) removed -- arithmetic assignment gone, arithmetic guard kept.   *)
(***************************************************************************)
THEOREM B2 == ASSUME NEW k \in Orderers
              PROVE  (Typed /\ state[k] = "follower" /\ currentTerm[k] < MaxTerm)
                     => ENABLED <<StepNoArith>>_vars
  BY ExpandENABLED DEF Typed, TypeOK, StepNoArith, CampNoArith, vars

(***************************************************************************)
(* B3  (c) reduced -- two assignments, both arithmetic features kept.      *)
(***************************************************************************)
THEOREM B3 == ASSUME NEW k \in Orderers
              PROVE  (Typed /\ state[k] = "follower" /\ currentTerm[k] < MaxTerm)
                     => ENABLED <<StepTwo>>_vars
  BY ExpandENABLED DEF Typed, TypeOK, StepTwo, CampTwo, vars

(***************************************************************************)
(* B4  full Campaign, same proof text.  Expected: FAILS.                   *)
(***************************************************************************)
THEOREM B4 == ASSUME NEW k \in Orderers
              PROVE  (Typed /\ state[k] = "follower" /\ currentTerm[k] < MaxTerm)
                     => ENABLED <<CampStep>>_vars
  BY ExpandENABLED DEF Typed, TypeOK, CampStep, Campaign, vars

=============================================================================
