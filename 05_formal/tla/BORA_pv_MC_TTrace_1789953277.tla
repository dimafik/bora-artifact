---- MODULE BORA_pv_MC_TTrace_1789953277 ----
EXTENDS Sequences, TLCExt, BORA_pv_MC_TEConstants, Toolbox, Naturals, TLC, BORA_pv_MC

_expression ==
    LET BORA_pv_MC_TEExpression == INSTANCE BORA_pv_MC_TEExpression
    IN BORA_pv_MC_TEExpression!expression
----

_trace ==
    LET BORA_pv_MC_TETrace == INSTANCE BORA_pv_MC_TETrace
    IN BORA_pv_MC_TETrace!trace
----

_inv ==
    ~(
        TLCGet("level") = Len(_TETrace)
        /\
        failOpen = (FALSE)
        /\
        leader = ((0 :> 0 @@ 1 :> 1))
        /\
        votedFor = (<<1, 0, 0>>)
        /\
        blSeq = (1)
        /\
        currentTerm = (<<1, 0, 0>>)
        /\
        log = (<<<<>>, <<>>, <<>>>>)
        /\
        blacklist = (<<{1}, {}, {1}>>)
        /\
        state = (<<"leader", "follower", "follower">>)
        /\
        history = (<<>>)
        /\
        commitIndex = (<<0, 0, 0>>)
    )
----

_init ==
    /\ state = _TETrace[1].state
    /\ failOpen = _TETrace[1].failOpen
    /\ currentTerm = _TETrace[1].currentTerm
    /\ blSeq = _TETrace[1].blSeq
    /\ blacklist = _TETrace[1].blacklist
    /\ history = _TETrace[1].history
    /\ leader = _TETrace[1].leader
    /\ votedFor = _TETrace[1].votedFor
    /\ commitIndex = _TETrace[1].commitIndex
    /\ log = _TETrace[1].log
----

_next ==
    /\ \E i,j \in DOMAIN _TETrace:
        /\ \/ /\ j = i + 1
              /\ i = TLCGet("level")
        /\ state  = _TETrace[i].state
        /\ state' = _TETrace[j].state
        /\ failOpen  = _TETrace[i].failOpen
        /\ failOpen' = _TETrace[j].failOpen
        /\ currentTerm  = _TETrace[i].currentTerm
        /\ currentTerm' = _TETrace[j].currentTerm
        /\ blSeq  = _TETrace[i].blSeq
        /\ blSeq' = _TETrace[j].blSeq
        /\ blacklist  = _TETrace[i].blacklist
        /\ blacklist' = _TETrace[j].blacklist
        /\ history  = _TETrace[i].history
        /\ history' = _TETrace[j].history
        /\ leader  = _TETrace[i].leader
        /\ leader' = _TETrace[j].leader
        /\ votedFor  = _TETrace[i].votedFor
        /\ votedFor' = _TETrace[j].votedFor
        /\ commitIndex  = _TETrace[i].commitIndex
        /\ commitIndex' = _TETrace[j].commitIndex
        /\ log  = _TETrace[i].log
        /\ log' = _TETrace[j].log

\* Uncomment the ASSUME below to write the states of the error trace
\* to the given file in Json format. Note that you can pass any tuple
\* to `JsonSerialize`. For example, a sub-sequence of _TETrace.
    \* ASSUME
    \*     LET J == INSTANCE Json
    \*         IN J!JsonSerialize("BORA_pv_MC_TTrace_1789953277.json", _TETrace)

=============================================================================

 Note that you can extract this module `BORA_pv_MC_TEExpression`
  to a dedicated file to reuse `expression` (the module in the 
  dedicated `BORA_pv_MC_TEExpression.tla` file takes precedence 
  over the module `BORA_pv_MC_TEExpression` below).

---- MODULE BORA_pv_MC_TEExpression ----
EXTENDS Sequences, TLCExt, BORA_pv_MC_TEConstants, Toolbox, Naturals, TLC, BORA_pv_MC

expression == 
    [
        \* To hide variables of the `BORA_pv_MC` spec from the error trace,
        \* remove the variables below.  The trace will be written in the order
        \* of the fields of this record.
        state |-> state
        ,failOpen |-> failOpen
        ,currentTerm |-> currentTerm
        ,blSeq |-> blSeq
        ,blacklist |-> blacklist
        ,history |-> history
        ,leader |-> leader
        ,votedFor |-> votedFor
        ,commitIndex |-> commitIndex
        ,log |-> log
        
        \* Put additional constant-, state-, and action-level expressions here:
        \* ,_stateNumber |-> _TEPosition
        \* ,_stateUnchanged |-> state = state'
        
        \* Format the `state` variable as Json value.
        \* ,_stateJson |->
        \*     LET J == INSTANCE Json
        \*     IN J!ToJson(state)
        
        \* Lastly, you may build expressions over arbitrary sets of states by
        \* leveraging the _TETrace operator.  For example, this is how to
        \* count the number of times a spec variable changed up to the current
        \* state in the trace.
        \* ,_stateModCount |->
        \*     LET F[s \in DOMAIN _TETrace] ==
        \*         IF s = 1 THEN 0
        \*         ELSE IF _TETrace[s].state # _TETrace[s-1].state
        \*             THEN 1 + F[s-1] ELSE F[s-1]
        \*     IN F[_TEPosition - 1]
    ]

=============================================================================



Parsing and semantic processing can take forever if the trace below is long.
 In this case, it is advised to uncomment the module below to deserialize the
 trace from a generated binary file.

\*
\*---- MODULE BORA_pv_MC_TETrace ----
\*EXTENDS IOUtils, BORA_pv_MC_TEConstants, TLC, BORA_pv_MC
\*
\*trace == IODeserialize("BORA_pv_MC_TTrace_1789953277.bin", TRUE)
\*
\*=============================================================================
\*

---- MODULE BORA_pv_MC_TETrace ----
EXTENDS BORA_pv_MC_TEConstants, TLC, BORA_pv_MC

trace == 
    <<
    ([failOpen |-> FALSE,leader |-> (0 :> 0 @@ 1 :> 0),votedFor |-> <<0, 0, 0>>,blSeq |-> 0,currentTerm |-> <<0, 0, 0>>,log |-> <<<<>>, <<>>, <<>>>>,blacklist |-> <<{}, {}, {}>>,state |-> <<"follower", "follower", "follower">>,history |-> <<>>,commitIndex |-> <<0, 0, 0>>]),
    ([failOpen |-> FALSE,leader |-> (0 :> 0 @@ 1 :> 0),votedFor |-> <<1, 0, 0>>,blSeq |-> 0,currentTerm |-> <<1, 0, 0>>,log |-> <<<<>>, <<>>, <<>>>>,blacklist |-> <<{}, {}, {}>>,state |-> <<"candidate", "follower", "follower">>,history |-> <<>>,commitIndex |-> <<0, 0, 0>>]),
    ([failOpen |-> FALSE,leader |-> (0 :> 0 @@ 1 :> 0),votedFor |-> <<1, 0, 0>>,blSeq |-> 1,currentTerm |-> <<1, 0, 0>>,log |-> <<<<>>, <<>>, <<>>>>,blacklist |-> <<{1}, {}, {1}>>,state |-> <<"candidate", "follower", "follower">>,history |-> <<>>,commitIndex |-> <<0, 0, 0>>]),
    ([failOpen |-> FALSE,leader |-> (0 :> 0 @@ 1 :> 1),votedFor |-> <<1, 0, 0>>,blSeq |-> 1,currentTerm |-> <<1, 0, 0>>,log |-> <<<<>>, <<>>, <<>>>>,blacklist |-> <<{1}, {}, {1}>>,state |-> <<"leader", "follower", "follower">>,history |-> <<>>,commitIndex |-> <<0, 0, 0>>])
    >>
----


=============================================================================

---- MODULE BORA_pv_MC_TEConstants ----
EXTENDS BORA_pv_MC

CONSTANTS v1

=============================================================================

---- CONFIG BORA_pv_MC_TTrace_1789953277 ----
CONSTANTS
    N = 3
    F = 2
    MaxTerm = 1
    Values = { v1 }
    Orderers = { 1 , 2 , 3 }
    v1 = v1

INVARIANT
    _inv

CHECK_DEADLOCK
    \* CHECK_DEADLOCK off because of PROPERTY or INVARIANT above.
    FALSE

INIT
    _init

NEXT
    _next

CONSTANT
    _TETrace <- _trace

ALIAS
    _expression
=============================================================================
\* Generated on Mon Sep 21 10:14:38 KST 2026