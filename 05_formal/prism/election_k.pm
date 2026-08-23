// Round-bounded variant of election.pm (W=2): caps the number of election
// rounds at Kmax so that  P=? [F el]  yields  P[leader within Kmax rounds]
// = 1 - (1-q)^(Kmax+1), exhibiting the geometric decay directly.
dtmc

const int NE;           // eligible candidates
const int Kmax;         // round budget (swept 0,1,2,... to trace the curve)

module elect
  i    : [0..NE] init 0;
  minv : [0..2] init 2;
  uniq : bool init false;
  el   : bool init false;
  r    : [0..Kmax] init 0;

  [draw] (i<NE) & !el ->
      1/2 : (i'=i+1) & (minv'=min(0,minv)) & (uniq'=(0<minv)?true:((0=minv)?false:uniq))
    + 1/2 : (i'=i+1) & (minv'=min(1,minv)) & (uniq'=(1<minv)?true:((1=minv)?false:uniq));

  [ev] (i=NE) & !el & uniq            -> (el'=true);
  [ev] (i=NE) & !el & !uniq & r<Kmax  -> (i'=0)&(minv'=2)&(uniq'=false)&(r'=r+1);
  [ev] (i=NE) & !el & !uniq & r=Kmax  -> true;   // budget exhausted (self-loop, no deadlock)
endmodule
