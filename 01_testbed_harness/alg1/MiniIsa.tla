---- MODULE MiniIsa ----
EXTENDS Integers, Sequences, TLAPS
\* EXCEPT extraction WITHOUT domain (does SMT do select(store)=v unconditionally?)
LEMMA S1 == ASSUME NEW state, NEW j, NEW st, st = [state EXCEPT ![j] = "leader"]
            PROVE st[j] = "leader" BY SMT
LEMMA S2 == ASSUME NEW state, NEW j, NEW st, st = [state EXCEPT ![j] = "leader"]
            PROVE st[j] = "leader" BY st = [state EXCEPT ![j] = "leader"]
====
