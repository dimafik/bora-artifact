---- MODULE MiniFn ----
EXTENDS Integers, TLAPS
CONSTANT MaxTerm, N
ASSUME H == N >= 1 /\ MaxTerm >= 0
LEMMA FnZ == [t \in 0..MaxTerm |-> 0] \in [0..MaxTerm -> 0..N] BY Zenon, H
LEMMA FnA == [t \in 0..MaxTerm |-> 0] \in [0..MaxTerm -> 0..N] BY Auto, H
LEMMA FnS == [t \in 0..MaxTerm |-> 0] \in [0..MaxTerm -> 0..N] BY H, SMT
====
