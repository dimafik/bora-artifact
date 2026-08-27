# BORA — TLA+ / TLAPS development

Formal artefacts for Section IV-A (Theorem 1, Propositions 2 and 7) and
Section IV-E of the IEEE TNSE submission.

## What is here

| File | What it establishes | Result |
|---|---|---|
| `BORA.tla`, `BORA.cfg` | the augmented state machine; bounded model check at *N*=5, *f*=2, `MaxTerm`=3 | TLC, no violation |
| `BORA_MC.tla` | model-check wrapper | — |
| `BORA_proof.tla` | **Theorem 1**: `Spec => Vanilla!Spec`, a step-simulation refinement, **unbounded** | **TLAPS 48/48** |
| `BORA_pv.tla`, `BORA_pv_proof.tla` | the same refinement over a **per-voter** blacklist, `blacklist \in [Orderers -> SUBSET Orderers]`, views free to diverge | **TLAPS 48/48** |
| `BORA_pv_excl.tla` | **Proposition 7**: while a quorum holds *i* and the advisor has not failed open, *i* never acquires a term | **TLAPS 64/64** |
| `Liveness.tla` | **Proposition 2**: `SpecL => <>HasLeader` under weak fairness | **TLAPS 311/311, no axioms** |
| `Enabledness.tla`, `En*.tla` | independent TLC check of the two action-enabledness facts, plus positive and negative controls for the `ENABLED` tactic | 12/12 models pass |

`PROOF_RESULT.txt` is the full run log, including the mutation check that shows
the exclusion proof is not vacuous.

## How to run

```bash
# bounded model check
java -cp tla2tools.jar tlc2.TLC -config BORA.cfg BORA.tla -workers 4

# the deductive proofs (tlapm 1.5.0; --cleanfp forces a from-scratch run)
tlapm --cleanfp BORA_proof.tla        # 48 obligations
tlapm --cleanfp BORA_pv_proof.tla     # 48 obligations, per-voter
tlapm --cleanfp BORA_pv_excl.tla      # 64 obligations, exclusion
tlapm --cleanfp Liveness.tla          # 311 obligations, no axioms
```

## Scope, stated precisely

The refinement is proved **for every *N*, *f*, term and value**, not for a
model-checked instance. Vanilla etcdraft's own five safety invariants are cited
(Ongaro and Ousterhout) rather than re-derived; BORA inherits them through the
refinement. That is the content of Theorem 1: BORA adds no reachable behaviour to
vanilla Raft, so it cannot add a violation.

Liveness is **not** left to a backward-simulation sketch. The paper withdrew that
sketch; `Liveness.tla` proves Proposition 2 directly under weak fairness, and
both action-enabledness facts are proved theorems rather than axioms.

**Out of scope by construction, and not claimed anywhere:**

- The randomised-timeout *rate*. It is probabilistic, so it is not expressible in
  TLA+; it is verified separately in PRISM (`../prism/`).
- Real-time scheduling. Section IV-D of the paper explicitly declines to claim a
  schedulability proof and argues a timeout budget instead.
- The cryptographic boundary on the Unix-domain socket, a host-integrity
  assumption stated in Section II-C.
- Whether an honest quorum actually agrees inside a given election window. No
  protocol model can settle that; it is a deployment timing property and the
  paper reports it from the testbed.
