# Apalache Symbolic Model Checking

## Overview

`ISRaftMC_Apalache.tla` is an Apalache-compatible version of the
IS-Raft-MC TLA+ specification. Apalache uses SMT solvers (Z3) for
symbolic model checking, enabling verification of much larger
configurations than TLC.

## Differences from TLC

| Feature | TLC | Apalache |
|---|---|---|
| Backend | Enumeration | SMT (Z3) |
| Scale | $10^6$-$10^9$ states | $10^{12}+$ effective states |
| Types | Inferred | **Explicit (required)** |
| Speed | Linear in state space | Exponential in formula complexity |
| Memory | Linear | Bounded |
| Counterexamples | Concrete trace | Symbolic trace |

## Type Annotations (Required by Apalache)

Each variable has a `@type:` comment:
```tla
VARIABLES
    \* @type: SERVER -> Int;
    currentTerm,
    \* @type: SERVER -> STATE;
    state,
    ...
```

Each action has a `@type:` comment for parameters:
```tla
\* @type: (SERVER, MODE) => Bool;
SwitchMode(i, newMode) == ...
```

## Running Apalache

### Install

```bash
# Java 11+ required
brew install apalache
# Or download from https://apalache.informal.systems/
```

### Run

```bash
cd "D:/.../IS-Raft-LAC/formal/"
apalache-mc check \
  --inv=FullSafety \
  --length=20 \
  --init=Init \
  --next=Next \
  ISRaftMC_Apalache.tla
```

### Expected Output

```
Checker reports: No error up to computation length 20
Total time: ~10 minutes
```

## Configurations

### Small (5 minutes)
- Servers = {"s1", "s2", "s3"}
- Tasks = {"t1", "t2"}
- MaxTerm = 3
- MaxIndex = 5

### Medium (30 minutes)
- Servers = {"s1", "s2", "s3", "s4", "s5"}
- Tasks = {"t1", "t2", "t3", "t4"}
- MaxTerm = 5
- MaxIndex = 10

### Large (2 hours)
- Servers = {"s1", ..., "s7"}
- Tasks = {"t1", ..., "t6"}
- MaxTerm = 10
- MaxIndex = 20

## What Apalache Verifies

The same invariants as TLC, but over a larger state space:

1. **TypeOK**: type-safety of all variables.
2. **ElectionSafety**: at most one leader per term.
3. **LogMatching**: consistent log prefixes.
4. **LeaderCompleteness**: committed entries persist.
5. **StateMachineSafety**: no divergence.
6. **LogAppendOnly**: no overwrites.
7. **ModeSwitchSafety**: mode values valid.
8. **OracleAdvisorySafety**: safety holds under any oracle.
9. **WitnessBinding**: commitment values valid.

(For full CPL + PSR invariants from `ISRaftMC_v2_CPL.tla`, an
Apalache-compatible v2 file is future work.)

## Expected Bounds

Based on Apalache benchmarks for Raft-class specs:
- Medium config: ~30 minutes wall-clock
- Large config: 1-3 hours
- Memory: 4-8 GB

## Failure Modes

If Apalache reports a counterexample:
1. Inspect the trace at the reported step.
2. Check if it's a *real* bug or a *spec bug* (missing precondition).
3. Refine the spec; re-run.

## Comparison: TLC vs Apalache for Our Spec

| Aspect | TLC (10^7 states) | Apalache (10^12 states) |
|---|---|---|
| Configuration | 3 servers, 2 tasks | 7 servers, 6 tasks |
| Time | 1 hour | 2-3 hours |
| Coverage | Sufficient for correctness | Higher confidence |
| Counterexample | Concrete | Symbolic (more general) |

We recommend running **both**:
- TLC for fast iteration during development.
- Apalache for high-confidence final verification.

## Integration with CI/CD

Recommended workflow:
1. Each PR: run TLC on small config (5 min).
2. Each release: run Apalache on medium config (30 min).
3. Annual: run Apalache on large config (3 hours).

This provides continuous formal verification of the protocol's safety
invariants.

## Citation

Apalache paper: Igor Konnov, Jure Kukovec, Thanh-Hai Tran.
"TLA+ Model Checking Made Symbolic." OOPSLA 2019.

URL: https://apalache.informal.systems/
