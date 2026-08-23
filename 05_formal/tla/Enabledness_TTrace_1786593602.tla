---- MODULE Enabledness_TTrace_1786593602 ----
EXTENDS Sequences, TLCExt, Toolbox, Naturals, TLC, Enabledness_TEConstants, Enabledness

_expression ==
    LET Enabledness_TEExpression == INSTANCE Enabledness_TEExpression
    IN Enabledness_TEExpression!expression
----

_trace ==
    LET Enabledness_TETrace == INSTANCE Enabledness_TETrace
    IN Enabledness_TETrace!trace
----

_inv ==
    ~(
        TLCGet("level") = Len(_TETrace)
        /\
        leader = ((0 :> 0 @@ 1 :> 0 @@ 2 :> 0 @@ 3 :> 0))
        /\
        votedFor = (<<1, 2, 3, 4, 5>>)
        /\
        currentTerm = (<<1, 1, 1, 1, 1>>)
        /\
        log = (<<<<>>, <<>>, <<>>, <<>>, <<>>>>)
        /\
        state = (<<"candidate", "candidate", "candidate", "candidate", "candidate">>)
        /\
        history = (<<>>)
        /\
        commitIndex = (<<0, 0, 0, 0, 0>>)
    )
----

_init ==
    /\ leader = _TETrace[1].leader
    /\ log = _TETrace[1].log
    /\ state = _TETrace[1].state
    /\ commitIndex = _TETrace[1].commitIndex
    /\ history = _TETrace[1].history
    /\ currentTerm = _TETrace[1].currentTerm
    /\ votedFor = _TETrace[1].votedFor
----

_next ==
    /\ \E i,j \in DOMAIN _TETrace:
        /\ \/ /\ j = i + 1
              /\ i = TLCGet("level")
        /\ leader  = _TETrace[i].leader
        /\ leader' = _TETrace[j].leader
        /\ log  = _TETrace[i].log
        /\ log' = _TETrace[j].log
        /\ state  = _TETrace[i].state
        /\ state' = _TETrace[j].state
        /\ commitIndex  = _TETrace[i].commitIndex
        /\ commitIndex' = _TETrace[j].commitIndex
        /\ history  = _TETrace[i].history
        /\ history' = _TETrace[j].history
        /\ currentTerm  = _TETrace[i].currentTerm
        /\ currentTerm' = _TETrace[j].currentTerm
        /\ votedFor  = _TETrace[i].votedFor
        /\ votedFor' = _TETrace[j].votedFor

\* Uncomment the ASSUME below to write the states of the error trace
\* to the given file in Json format. Note that you can pass any tuple
\* to `JsonSerialize`. For example, a sub-sequence of _TETrace.
    \* ASSUME
    \*     LET J == INSTANCE Json
    \*         IN J!JsonSerialize("Enabledness_TTrace_1786593602.json", _TETrace)

=============================================================================

 Note that you can extract this module `Enabledness_TEExpression`
  to a dedicated file to reuse `expression` (the module in the 
  dedicated `Enabledness_TEExpression.tla` file takes precedence 
  over the module `Enabledness_TEExpression` below).

---- MODULE Enabledness_TEExpression ----
EXTENDS Sequences, TLCExt, Toolbox, Naturals, TLC, Enabledness_TEConstants, Enabledness

expression == 
    [
        \* To hide variables of the `Enabledness` spec from the error trace,
        \* remove the variables below.  The trace will be written in the order
        \* of the fields of this record.
        leader |-> leader
        ,log |-> log
        ,state |-> state
        ,commitIndex |-> commitIndex
        ,history |-> history
        ,currentTerm |-> currentTerm
        ,votedFor |-> votedFor
        
        \* Put additional constant-, state-, and action-level expressions here:
        \* ,_stateNumber |-> _TEPosition
        \* ,_leaderUnchanged |-> leader = leader'
        
        \* Format the `leader` variable as Json value.
        \* ,_leaderJson |->
        \*     LET J == INSTANCE Json
        \*     IN J!ToJson(leader)
        
        \* Lastly, you may build expressions over arbitrary sets of states by
        \* leveraging the _TETrace operator.  For example, this is how to
        \* count the number of times a spec variable changed up to the current
        \* state in the trace.
        \* ,_leaderModCount |->
        \*     LET F[s \in DOMAIN _TETrace] ==
        \*         IF s = 1 THEN 0
        \*         ELSE IF _TETrace[s].leader # _TETrace[s-1].leader
        \*             THEN 1 + F[s-1] ELSE F[s-1]
        \*     IN F[_TEPosition - 1]
    ]

=============================================================================



Parsing and semantic processing can take forever if the trace below is long.
 In this case, it is advised to uncomment the module below to deserialize the
 trace from a generated binary file.

\*
\*---- MODULE Enabledness_TETrace ----
\*EXTENDS IOUtils, TLC, Enabledness_TEConstants, Enabledness
\*
\*trace == IODeserialize("Enabledness_TTrace_1786593602.bin", TRUE)
\*
\*=============================================================================
\*

---- MODULE Enabledness_TETrace ----
EXTENDS TLC, Enabledness_TEConstants, Enabledness

trace == 
    <<
    ([leader |-> (0 :> 0 @@ 1 :> 0 @@ 2 :> 0 @@ 3 :> 0),votedFor |-> <<0, 0, 0, 0, 0>>,currentTerm |-> <<0, 0, 0, 0, 0>>,log |-> <<<<>>, <<>>, <<>>, <<>>, <<>>>>,state |-> <<"follower", "follower", "follower", "follower", "follower">>,history |-> <<>>,commitIndex |-> <<0, 0, 0, 0, 0>>]),
    ([leader |-> (0 :> 0 @@ 1 :> 0 @@ 2 :> 0 @@ 3 :> 0),votedFor |-> <<1, 0, 0, 0, 0>>,currentTerm |-> <<1, 0, 0, 0, 0>>,log |-> <<<<>>, <<>>, <<>>, <<>>, <<>>>>,state |-> <<"candidate", "follower", "follower", "follower", "follower">>,history |-> <<>>,commitIndex |-> <<0, 0, 0, 0, 0>>]),
    ([leader |-> (0 :> 0 @@ 1 :> 0 @@ 2 :> 0 @@ 3 :> 0),votedFor |-> <<1, 2, 0, 0, 0>>,currentTerm |-> <<1, 1, 0, 0, 0>>,log |-> <<<<>>, <<>>, <<>>, <<>>, <<>>>>,state |-> <<"candidate", "candidate", "follower", "follower", "follower">>,history |-> <<>>,commitIndex |-> <<0, 0, 0, 0, 0>>]),
    ([leader |-> (0 :> 0 @@ 1 :> 0 @@ 2 :> 0 @@ 3 :> 0),votedFor |-> <<1, 2, 3, 0, 0>>,currentTerm |-> <<1, 1, 1, 0, 0>>,log |-> <<<<>>, <<>>, <<>>, <<>>, <<>>>>,state |-> <<"candidate", "candidate", "candidate", "follower", "follower">>,history |-> <<>>,commitIndex |-> <<0, 0, 0, 0, 0>>]),
    ([leader |-> (0 :> 0 @@ 1 :> 0 @@ 2 :> 0 @@ 3 :> 0),votedFor |-> <<1, 2, 3, 4, 0>>,currentTerm |-> <<1, 1, 1, 1, 0>>,log |-> <<<<>>, <<>>, <<>>, <<>>, <<>>>>,state |-> <<"candidate", "candidate", "candidate", "candidate", "follower">>,history |-> <<>>,commitIndex |-> <<0, 0, 0, 0, 0>>]),
    ([leader |-> (0 :> 0 @@ 1 :> 0 @@ 2 :> 0 @@ 3 :> 0),votedFor |-> <<1, 2, 3, 4, 5>>,currentTerm |-> <<1, 1, 1, 1, 1>>,log |-> <<<<>>, <<>>, <<>>, <<>>, <<>>>>,state |-> <<"candidate", "candidate", "candidate", "candidate", "candidate">>,history |-> <<>>,commitIndex |-> <<0, 0, 0, 0, 0>>])
    >>
----


=============================================================================

---- MODULE Enabledness_TEConstants ----
EXTENDS Enabledness

CONSTANTS v1, v2

=============================================================================

---- CONFIG Enabledness_TTrace_1786593602 ----
CONSTANTS
    N = 5
    F = 2
    MaxTerm = 3
    Values = { v1 , v2 }
    v1 = v1
    v2 = v2

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
\* Generated on Thu Aug 13 13:00:03 KST 2026