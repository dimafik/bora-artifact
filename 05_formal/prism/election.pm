// =====================================================================
// BORA leader-election convergence -- probabilistic rate (PRISM DTMC).
//
// This mechanises the PROBABILISTIC part of Proposition (liveness) that
// (non-probabilistic) TLA+/TLAPS cannot express.  Within BORA's eligible
// set E_t = { i : i \notin B_t } (the minimum-hold rule keeps |E_t| >=
// ceil((N+1)/2) for the hold window; blacklisted nodes withhold their
// campaign but still grant votes), the surviving nodes run vanilla Raft's
// randomised election timeout.  Each round, every eligible candidate draws
// a uniform timeout slot in {0,..,W-1}; the candidate with the UNIQUE
// smallest slot times out first and wins; a tie for the smallest slot is a
// split vote and the round repeats.  W=2 is modelled here (the smallest /
// most adversarial window -> largest split probability); larger W only
// speeds convergence.  NE = |E_t| is the number of eligible candidates.
//
// Verified (see election.props):  P>=1 [F elected]   (w.p.1 a leader is
// elected) and the geometric decay  P[no leader after k rounds] = (1-q)^k.
// =====================================================================
dtmc

const int NE;           // |E_t| eligible candidates (3,4,5 for N=5, |B_t|<=2)

module elect
  i    : [0..NE] init 0;  // candidates that have drawn a slot this round
  minv : [0..2] init 2;   // smallest slot drawn so far (2 = +inf sentinel; W=2 slots {0,1})
  uniq : bool init false; // smallest slot currently held by exactly one node
  el   : bool init false; // leader elected (absorbing)

  // draw phase: each eligible candidate draws a uniform slot in {0,1}
  [draw] (i<NE) & !el ->
      1/2 : (i'=i+1) & (minv'=min(0,minv)) & (uniq'=(0<minv)?true:((0=minv)?false:uniq))
    + 1/2 : (i'=i+1) & (minv'=min(1,minv)) & (uniq'=(1<minv)?true:((1=minv)?false:uniq));

  // evaluate phase: unique earliest -> leader; tie -> fresh round
  [ev] (i=NE) & !el & uniq  -> (el'=true);
  [ev] (i=NE) & !el & !uniq -> (i'=0) & (minv'=2) & (uniq'=false);
endmodule

// one unit of reward per completed election round (until a leader is elected)
rewards "rounds"
  [ev] !el : 1;
endrewards
