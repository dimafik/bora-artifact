# TLA+ Formal Verification Log

## Specifications

| File | Content | Status |
|---|---|---|
| `ISRaftMC.tla` | v1: 8 safety invariants (5 Raft + 3 IS-Raft-MC) | Drafted |
| `ISRaftMC_v2_CPL.tla` | v2: + CPL, PSR, Schedulability, Reclamation | **NEW** |

## Invariants in v2 (12 total)

### Inherited Raft (5)
1. ElectionSafety: at most one leader per term
2. LogMatching: same (index, term) ⇒ identical prefix
3. LeaderCompleteness: committed entries in all future leaders
4. StateMachineSafety: no diverging applied states
5. LogAppendOnly: no log overwrites

### IS-Raft-MC v1 (3)
6. ModeSwitchSafety: CRITICAL mode preserves commits
7. OracleAdvisorySafety: invariants hold under any oracle output
8. WitnessBinding: KZG commit binds prediction

### NEW CPL/PSR v2 (4)
9. **CPLInvariant**: $|\hat{\tau} - \tau| \leq \zeta$ AND $\hat{\tau} \leq \kappa \tau$ AND distribution-aware
10. **PSRStrictPriority**: LC commits blocked while HC tasks exist + mid-point not reached
11. **SchedulabilityInvariant**: every committed task's actual time ≤ deadline
12. **ReclamationInvariant**: reclamation count monotonic within epoch

## Theorems

### Theorem CPLImpliesSchedulability (Theorem 4 of TNSE paper)
$$\text{Spec} \Rightarrow \Box \left( (\text{CPL} \wedge \kappa \leq 1.5 \wedge \zeta \leq 0.5)
   \Rightarrow \text{SchedulabilityInvariant} \right)$$

### Theorem PSRTheorem (Theorem 3.5 of TNSE paper)
$$\text{Spec} \Rightarrow \Box \left( \text{PSRStrictPriority} \wedge \text{ReclamationInvariant} \right)$$

### Theorem SafetyHolds (Theorem 9.1 of TNSE paper)
$$\text{Spec} \Rightarrow \Box \text{FullSafety}$$

## TLC Model Checker Configuration

```
SPECIFICATION Spec
INVARIANTS
    FullSafety
    CPLInvariant
    PSRStrictPriority
    SchedulabilityInvariant
    ReclamationInvariant

CONSTANTS
    Servers = {s1, s2, s3}
    HC = "HC"
    LC = "LC"
    PB = "PB"
    Tasks = {t1, t2, t3}
    Deadlines = (t1 :> 10.0 @@ t2 :> 20.0 @@ t3 :> 30.0)
    MaxTerm = 3
    MaxIndex = 5
    Zeta = 0.5
    Kappa = 1.5
    Null = NULL
```

## Expected Verification Outcomes

With the above configuration (3 servers, 3 tasks):
- Approximate state space: ~10^8 states
- Expected wall-clock time: ~1-2 hours on 16-core machine
- Memory: ~16 GB

**Expected outcome:** All 12 invariants verified.

For larger configurations, use Apalache (symbolic):
```bash
apalache check --inv=FullSafety ISRaftMC_v2_CPL.tla
```

## Verification Validity vs Theorem Validity

The TLA+ verification machine-checks a **finite-state abstraction** of
the protocol. Theorems in the TNSE paper apply to the **infinite-state**
real protocol.

This is the standard relationship in formal verification:
- TLA+ proves invariants hold for *every state* of the abstract model.
- Mathematical proofs in the paper apply for *every parameter value*.

The two are complementary:
- TLA+: catches *logical errors* in the protocol design (e.g., missing
  case in state transition).
- Mathematical proofs: establish *quantitative bounds* (e.g., 270×
  improvement).

## Limitations of Current TLA+ Spec

1. **Bounded model checking:** TLC verifies finite configurations.
   Larger configurations require symbolic model checking (Apalache).

2. **Abstraction over time:** TLA+ has no built-in real-time semantics;
   we represent time as discrete state variables.

3. **CPL approximation:** The CPL invariant is encoded as state
   constraints; the empirical CPL from §11 measurements is a separate
   validation.

4. **Schedulability simplification:** SchedulabilityInvariant uses
   per-task deadline mapping; production has per-channel policy.

## Next Steps for Full Verification

1. **Apalache symbolic check** with 7+ servers, 10+ tasks.
2. **Coq proof** of CPLImpliesSchedulability with full real-number
   reasoning.
3. **Refinement chain:** TLA+ → Coq → Python implementation, all
   verifying same invariants.

These are Paper-3 follow-up directions.
