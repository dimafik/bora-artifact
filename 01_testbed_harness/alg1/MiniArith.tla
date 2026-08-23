---- MODULE MiniArith ----
EXTENDS Integers, TLAPS
CONSTANT N, MaxTerm
VARIABLE leader
ASSUME NA == N >= 1 /\ MaxTerm >= 1
\* function-application membership (the kind that failed under zenon AND z3)
LEMMA Mem == (leader \in [0..MaxTerm -> 0..N] /\ 3 \in 0..MaxTerm) => leader[3] \in 0..N
  BY Auto
LEMMA MemZ == (leader \in [0..MaxTerm -> 0..N] /\ 3 \in 0..MaxTerm) => leader[3] \in 0..N
  BY Zenon
LEMMA MemF == (leader \in [0..MaxTerm -> 0..N] /\ 3 \in 0..MaxTerm) => leader[3] \in 0..N
  BY Force
====
