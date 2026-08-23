// Window-sensitivity check: same election DTMC with a wider timeout window
// W=3 (slots {0,1,2}).  A wider window lowers the split probability, so the
// per-round success q rises and convergence is faster -- confirming that the
// W=2 figures in election.pm are the adversarial worst case.  NE = |E_t|.
dtmc

const int NE;

module elect
  i    : [0..NE] init 0;
  minv : [0..3] init 3;   // 3 = +inf sentinel; W=3 slots {0,1,2}
  uniq : bool init false;
  el   : bool init false;

  [draw] (i<NE) & !el ->
      1/3 : (i'=i+1) & (minv'=min(0,minv)) & (uniq'=(0<minv)?true:((0=minv)?false:uniq))
    + 1/3 : (i'=i+1) & (minv'=min(1,minv)) & (uniq'=(1<minv)?true:((1=minv)?false:uniq))
    + 1/3 : (i'=i+1) & (minv'=min(2,minv)) & (uniq'=(2<minv)?true:((2=minv)?false:uniq));

  [ev] (i=NE) & !el & uniq  -> (el'=true);
  [ev] (i=NE) & !el & !uniq -> (i'=0) & (minv'=3) & (uniq'=false);
endmodule

rewards "rounds"
  [ev] !el : 1;
endrewards
