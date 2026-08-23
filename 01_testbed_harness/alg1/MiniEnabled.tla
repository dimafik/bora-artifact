---- MODULE MiniEnabled ----
EXTENDS Integers, TLAPS
VARIABLE x
vars == <<x>>
A == x' = x + 1
LEMMA En_def == TRUE => ENABLED <<A>>_vars BY DEF A, vars
LEMMA En_auto == TRUE => ENABLED <<A>>_vars BY Auto DEF A, vars
LEMMA En_force == TRUE => ENABLED <<A>>_vars BY Force DEF A, vars
====
