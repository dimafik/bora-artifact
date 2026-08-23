--------------------------- MODULE BORA_MC ----------------------------
(***************************************************************************)
(* TLC model-checking instance of BORA with small finite bounds.           *)
(***************************************************************************)
EXTENDS BORA

CONSTANTS
    N_MC,
    F_MC,
    MaxTerm_MC,
    Values_MC

\* Bind the BORA constants to small-model values for TLC.
\* Use a 5-orderer, f=2, 3-term, 2-value model.
\* This is the smallest model that exhibits all five Raft invariants
\* under a non-empty blacklist.

=============================================================================
