# Generate G1 (PRISM convergence) and G2 (exclusion forest) from REAL data.
# Academic muted palette + Arial, vector PDF for LaTeX.
import re, math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import rcParams

rcParams["font.family"] = "Arial"
rcParams["font.size"] = 9
rcParams["axes.linewidth"] = 0.7
rcParams["pdf.fonttype"] = 42   # editable/embedded TrueType

NAVY="#25405c"; BURG="#8a3a45"; FOREST="#3a6b4a"; MUST="#c08a2e"; SLATE="#5b6670"
FIGDIR=r"D:\프랑스 업데이트\TNSE 스페셜이슈 논문\IS-Raft-LAC\submission\figures"

# ---------- G1: PRISM geometric convergence ----------
sweep=open(r"D:\fabric-d2\alg1\prism_sweep.txt",encoding="utf-8").read()
data={3:{},4:{},5:{}}
for m in re.finditer(r"NE=(\d+) K=(\d+) P=([0-9.]+)", sweep):
    ne,k,p=int(m.group(1)),int(m.group(2)),float(m.group(3))
    data[ne][k+1]=p          # Kmax=K -> up to K+1 rounds
q={3:3/8,4:4/16,5:5/32}      # P[within 1 round] = per-round success q = NE/2^NE
styles={3:(FOREST,"o","$|E_t|{=}3$  ($E[$rounds$]{=}2.7$)"),
        4:(MUST,"s","$|E_t|{=}4$  ($E[$rounds$]{=}4.0$)"),
        5:(NAVY,"^","$|E_t|{=}5$  ($E[$rounds$]{=}6.4$)")}

fig,ax=plt.subplots(figsize=(3.4,2.5))
ax.axhline(1.0,ls=(0,(4,3)),lw=0.8,color=SLATE,alpha=0.8)
ax.text(14.3,1.012,"w.p. 1",fontsize=7.5,color=SLATE,ha="right")
for ne in (5,4,3):
    xs=[1]+sorted(data[ne]); ys=[q[ne]]+[data[ne][x] for x in sorted(data[ne])]
    c,mk,lab=styles[ne]
    ax.plot(xs,ys,marker=mk,ms=3.2,lw=1.3,color=c,label=lab,markerfacecolor="white",markeredgewidth=0.9)
ax.set_xlabel("Election rounds $k$"); ax.set_ylabel(r"$\Pr[\,$leader within $k$ rounds$\,]$")
ax.set_xlim(0.5,15); ax.set_ylim(0,1.06); ax.set_xticks([1,3,5,7,9,11,13,15])
ax.legend(loc="lower right",fontsize=7,frameon=False,handlelength=1.6)
ax.grid(True,lw=0.4,alpha=0.35)
ax.set_title("Leader-election convergence (PRISM DTMC, $W{=}2$ worst case)",fontsize=8)
for s in ("top","right"): ax.spines[s].set_visible(False)
fig.tight_layout(pad=0.3)
fig.savefig(FIGDIR+r"\fig_prism_convergence.pdf",bbox_inches="tight")
print("G1 saved")

# ---------- G2: exclusion robustness forest ----------
def wilson(k,n,z=1.96):
    p=k/n; d=1+z*z/n
    c=(p+z*z/(2*n))/d
    h=(z/d)*math.sqrt(p*(1-p)/n + z*z/(4*n*n))
    return max(0,c-h)*100, c*100, min(1,c+h)*100, p*100
# config: (label, baseline k/n, BORA k/n)
cfgs=[("$N{=}5$ single-host",(7,36),(0,36)),
      ("$N{=}7$ scaling",(7,20),(0,20)),
      ("$N{=}9$ scaling",(4,20),(0,20)),
      ("physical 5-host AWS",(2,16),(0,16))]
fig2,ax2=plt.subplots(figsize=(3.4,2.4))
ys=list(range(len(cfgs)))[::-1]
for y,(lab,(bk,bn),(ak,an)) in zip(ys,cfgs):
    bl,bc,bu,bp=wilson(bk,bn); al,ac,au,ap=wilson(ak,an)
    ax2.plot([bl,bu],[y+0.13,y+0.13],color=BURG,lw=1.4,solid_capstyle="round")
    ax2.plot(bp,y+0.13,"o",ms=4.5,color=BURG,markerfacecolor="white",markeredgewidth=1.1)
    ax2.plot([al,au],[y-0.13,y-0.13],color=NAVY,lw=1.4,solid_capstyle="round")
    ax2.plot(ap,y-0.13,"s",ms=4.2,color=NAVY)
    ax2.text(au+1.2,y-0.13,f"≤{au:.1f}%",fontsize=6.8,color=NAVY,va="center")
ax2.set_yticks(ys); ax2.set_yticklabels([c[0] for c in cfgs],fontsize=7.5)
ax2.set_ylim(-0.6,len(cfgs)-0.4); ax2.set_xlim(-2,62)
ax2.set_xlabel("Leadership acquisition (%), 95% Wilson CI")
ax2.axvline(0,ls=(0,(4,3)),lw=0.7,color=SLATE,alpha=0.6)
from matplotlib.lines import Line2D
ax2.legend(handles=[Line2D([0],[0],color=BURG,marker="o",markerfacecolor="white",lw=1.4,label="baseline Raft"),
                    Line2D([0],[0],color=NAVY,marker="s",lw=1.4,label="BORA")],
           loc="lower right",fontsize=7,frameon=False,handlelength=1.6)
ax2.grid(True,axis="x",lw=0.4,alpha=0.35)
ax2.set_title("Leadership-acquisition exclusion across configurations",fontsize=8)
for s in ("top","right"): ax2.spines[s].set_visible(False)
fig2.tight_layout(pad=0.3)
fig2.savefig(FIGDIR+r"\fig_exclusion_forest.pdf",bbox_inches="tight")
print("G2 saved")
# print the numbers used (for caption/verification)
for lab,(bk,bn),(ak,an) in cfgs:
    print(f"{lab}: baseline {bk}/{bn}={100*bk/bn:.1f}% CI[{wilson(bk,bn)[0]:.1f},{wilson(bk,bn)[2]:.1f}]  BORA {ak}/{an}=0% CI<={wilson(ak,an)[2]:.1f}%")
