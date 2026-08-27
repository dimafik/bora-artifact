# BORA — formal artefacts

Machine-checked material for the IEEE TNSE submission
*"BORA: A Bounded Order-Risk Advisor for Provably Safe ML-Augmented Leader
Election in Raft Consensus"*.

| Directory | Contents |
|---|---|
| [`tla/`](tla/) | TLA+ specifications and TLAPS proofs for Theorem 1 (augmentation safety), Proposition 2 (liveness) and Proposition 7 (per-voter exclusion). See `tla/README.md` for the file-by-file map and `tla/PROOF_RESULT.txt` for the run log. |
| [`prism/`](prism/) | PRISM model and results for the randomised-timeout convergence rate, which is probabilistic and therefore outside TLA+. |

Headline results, all reproduced by the commands in `tla/README.md`:

- **Theorem 1**, `Spec => Vanilla!Spec`, proved for all *N*, *f*, terms and values
  — TLAPS, 48/48 obligations.
- **Proposition 2**, liveness under weak fairness — TLAPS, 311/311 obligations,
  **no axioms**.
- **Proposition 7**, exclusion under quorum agreement, over a per-voter blacklist
  — TLAPS, 64/64 obligations, with a mutation check showing the proof depends on
  the vote-grant guard.
- Bounded state exploration at *N*=5, *f*=2, `MaxTerm`=3 — TLC, no violation.
