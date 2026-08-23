---- MODULE MiniSuff ----
EXTENDS Integers, TLAPS
VARIABLE leader
CONSTANT MaxTerm, N
TypeOK == leader \in [0..MaxTerm -> 0..N]
Inv == TypeOK
\* T4: simple SUFFICES, single defined-op assumption
LEMMA T4 == Inv => leader \in [0..MaxTerm -> 0..N]
  <1>1. SUFFICES ASSUME Inv PROVE leader \in [0..MaxTerm -> 0..N] OBVIOUS
  <1>2. QED BY DEF Inv, TypeOK
\* T5: TAKE for forall, keep Inv as antecedent (T1-style)
LEMMA T5 == \A t \in 0..MaxTerm : (Inv => leader[t] \in 0..N)
  <1>1. TAKE t \in 0..MaxTerm
  <1>2. QED BY DEF Inv, TypeOK
\* T6: SUFFICES that introduces only NEW (no defined-op assumption), Inv stays in goal
LEMMA T6 == Inv => \A t \in 0..MaxTerm : leader[t] \in 0..N
  <1>1. SUFFICES \A t \in 0..MaxTerm : (Inv => leader[t] \in 0..N) OBVIOUS
  <1>2. TAKE t \in 0..MaxTerm
  <1>3. QED BY DEF Inv, TypeOK
====
