---- MODULE MiniLem ----
EXTENDS Integers, TLAPS
VARIABLE st
P == st = 0
Q == P /\ TRUE
Act(i) == st' = i
LEMMA L1 == ASSUME NEW i \in Nat PROVE (P /\ Act(i)) => st' = i
  BY DEF P, Act
THEOREM T == ASSUME NEW j \in Nat, Act(j) PROVE Q => st' = j
  <1>q. Q => P  BY DEF Q
  <1>2. QED BY <1>q, L1
====
