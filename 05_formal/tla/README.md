# BORA — TLA+ specification

This directory contains the TLA+ specification of the BORA-augmented
Hyperledger Fabric Raft state machine cited in §VII (Discussion) of
the IEEE TNSE Special Issue submission.

## Files
- `BORA.tla` — main spec (state, init, actions, invariants).
- `BORA.cfg` — TLC configuration (N=5, F=2, MaxTerm=3, |Values|=2).
- `BORA_MC.tla` — auxiliary model-check wrapper.

## How to run

```bash
java -cp tla2tools.jar tlc2.TLC -config BORA.cfg BORA.tla -workers 4
```

Expected output: TLC reports all eight invariants
(`TypeOK`, `BoundedCap`, `ALR_Inv`, `ElectionSafety`, `LogMatching`,
`StateMachineSafety`, `LeaderCompleteness`, and implicitly
`LeaderAppendOnly` via structural append) hold across the entire
reachable state space of the small model.

## What this checks

The model encodes the augmented protocol's transition system at the
abstraction level of Theorem 6's simulation relation:
1. BORA blacklist updates (`BoundedIntelligence`) project to `bot` and
   never violate the hard cap `|B_t| < f`.
2. Election (`Campaign`) yields on `i in B_t` without incrementing
   term — exactly the NoOp_i step of the simulation.
3. The five Raft safety invariants follow because the augmented
   transitions are a subset of the vanilla ones.

## What this does NOT check

- Liveness (the backward-simulation argument in §IV.A).
- Real-time scheduling (Liu–Layland; out of scope for TLA+).
- The cryptographic boundary on the UDS (assumed; out of scope).

## Relation to the paper

This spec discharges the proof obligations of Theorem 6 mechanically
for the N=5, F=2 instance. A full mechanisation across all model
parameters (or in Coq with a stronger meta-theory) is future work,
as flagged in §VII Discussion of the submission.
