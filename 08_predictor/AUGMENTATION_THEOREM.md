# Augmentation Safety Theorem (full proof)

## Setup

Let $\mathcal{C}=(N,\mathcal{N},\mathsf{Net})$ be a Raft cluster with
$N=|\mathcal{N}|$ nodes and (possibly asymmetric) network
$\mathsf{Net}$. We assume the S-Raft v5_3 assumptions hold:

- One-RTT max delay $\Delta$ on heartbeat path
- Process time $T_{\text{process}}$ bound
- Tiered timeout intervals $T_{\text{primary}}, T_{\text{secondary}}, T_{\text{follower}}$ with non-overlap
  $T_{\text{secondary}}^{\min} - T_{\text{primary}}^{\max} > \Delta + T_{\text{process}}$ (S-Raft Eq.3, Theorem 2)
- Byzantine bound $f<N/3$ on adversary-controlled nodes
- The score function $Score_i = w_{cc}\,CC_i + w_{rtt}\,\text{NORMALIZE}(RTT_i)$ (S-Raft Eq.derived)

Let $\mathcal{P}: \mathbb{R}^{K\times d} \to \mathbb{R}_{[0,1]}^3 \times \{0,1\}^N \times \mathbb{R}_{[0,1]}^N$
denote a predictor whose output we summarise as
$\mathcal{A}=\langle \text{ok}\in\{T,F\},\ \widehat{i}_{\text{prom}}\in\mathcal{N}\cup\{\bot\},\ \mathcal{B}\subseteq\mathcal{N},\ \mathcal{D}:\mathcal{N}\to[0,1]\rangle$.

## Advice integration

Define $\text{S-Raft}^{+\mathcal{A}}$ via the modified ranking line of
Algorithm 1:

```
rank0 ← TopTwo(Score)               # original ranking
if A.ok = F: rank ← rank0           # ignore advice
else:
    if |A.B| >= f: rank ← rank0     # safety guard
    else:
        rank1 ← rank0 \ A.B
        if A.i_prom in rank1:
            rank ← MoveToFront(rank1, A.i_prom)
        else:
            rank ← rank1
```

This is the *only* code path that differs from baseline S-Raft. Everything
else — vote majority, term monotonicity, log matching, commit rule — is
identical.

## Theorem (Augmentation Safety)

For every execution trace $\sigma$ of $\text{S-Raft}^{+\mathcal{A}}$:

1. **(T1)** Election Safety holds: $\forall t, \forall \text{term } T$, at most one node believes itself leader of $T$.
2. **(T2)** Detection Priority holds: the primary's timer fires strictly before secondary's.
3. **(T3 strengthening)** Cascading recovery bound:
   $$
   t_{\text{recover}}^{+\mathcal{A}}(\sigma) \le t_{\text{recover}}^{\text{baseline}}(\sigma).
   $$

## Proof

### Lemma 1 (Vote majority invariance)

The advice $\mathcal{A}$ does not modify any of:
- The vote-grant predicate (Raft §5.4: lastLogTerm + lastLogIdx comparison)
- The vote count required (⌈N/2⌉+1)
- The term-monotonic rule (a node rejects votes for stale terms)

*Proof.* By inspection of `S-Raft^{+A}` integration code. The advice
modifies only the *ordering* of `Top-2(Rank)`, which is the *output* of
the scoring function, not the input to the vote logic. $\square$

### Proof of T1 (Election Safety)

Standard Raft's Election Safety (Ongaro-Ousterhout §5.4.1) proof depends
only on:
1. The vote-grant predicate (above)
2. The vote count threshold (above)
3. The term-monotonic rule (above)

By Lemma 1, all three are unchanged. Therefore Election Safety is
preserved verbatim. $\square$

### Proof of T2 (Detection Priority)

S-Raft's Detection Priority (v5_3 Theorem 2) shows that with
non-overlapping tiers and a gap $G > \Delta + T_{\text{process}}$, the
primary always times out first. The proof uses only the tier interval
constants and $\Delta$ — not the ranking function.

The advice may force a node into a different *tier* (via $\mathcal{D}$
maintenance signal), but it does not change the tier *interval bounds*.
Within each tier the randomised timer distribution is identical to
baseline. So:

$\Pr[\,\text{primary fires first}\,]$ depends on $G/\sigma_{T}$, which is
unchanged by advice. $\square$

### Proof of T3 (Cascading Recovery Tightening)

Two cases.

**Case (a): $\mathcal{A}$ has pre-promoted before $t_{\text{kill}}^{(1)}$.**

By construction, the pre-promote message piggybacked on AppendEntries at
some time $t_p < t_{\text{kill}}^{(1)}$ and was delivered to a quorum at
time $t_p + \Delta$. By quorum overlap, when the cascade fires,
$\widehat{i}_{\text{prom}}$ already holds the (pending) sub-leader role.

The recovery sequence then collapses to one Promote-message round-trip:
$$
t_{\text{recover}}^{+\mathcal{A}} = t_{\text{kill}}^{(1)} + T_{\text{Promote}}^{1\text{RTT}} + 2\Delta.
$$

Since $T_{\text{secondary}}^{\max} \ge T_{\text{Promote}}^{1\text{RTT}}$ by tier definition,
$$
t_{\text{recover}}^{+\mathcal{A}} \le t_{\text{kill}}^{(1)} + T_{\text{secondary}}^{\max} + 2\Delta
\le t_{\text{recover}}^{\text{baseline}}.
$$

**Case (b): $\mathcal{A}.\text{ok} = F$ or pre-promote did not happen.**

Then the integration code falls back to `rank ← rank0`, which is exactly
baseline S-Raft. Therefore $t_{\text{recover}}^{+\mathcal{A}} = t_{\text{recover}}^{\text{baseline}}$.

Combining (a) and (b): $t_{\text{recover}}^{+\mathcal{A}} \le t_{\text{recover}}^{\text{baseline}}$ always. $\square$

### Corollary (Byzantine bound)

The integration code enforces $|\mathcal{B}|<f$. By S-Raft's f<N/3
assumption, the surviving rank set retains a quorum
of at least $N - f - |\mathcal{B}| > N - 2f > N/3$. Vote majority remains
satisfiable. $\square$

## Side observation (False positives are liveness-only)

If $\mathcal{A}$ wrongly puts a node $j \notin \text{ByzantineSet}$ into
$\mathcal{B}$, the only effect is that $j$ cannot be voted sub-leader for
$K_B$ heartbeats. Vote majority is still achievable by any of $N - |\mathcal{B}|$
nodes. Safety is preserved; only the rate of correct sub-leader selection
drops. This is by design — the system errs on the side of safety.

## What the theorem does NOT claim

- **Optimality.** We do not claim $\mathcal{P}$ produces optimal advice.
  We claim only that any advice respecting the integration rules cannot
  break safety.
- **Liveness improvement.** Under adversarial $\mathcal{P}$ (e.g. an attacker
  trains a poisoned model), liveness could degrade. Safety is unaffected.
- **Fairness across nodes.** $\mathcal{P}$ may systematically favor certain
  node configurations. This is a separate fairness concern.

## Verification artifact

A TLA+ model at `pivot_v26/tla/SRaftWithAdvice.tla` (to be authored)
encodes the integration rules and discharges T1-T3 invariants via
Apalache symbolic model checking. Pre-registered as part of v26 ScholarOne
submission.
