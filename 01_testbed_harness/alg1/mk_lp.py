# RETRACTED NUMBERS.  The AUC series 0.774/0.748/0.733/0.819 hardcoded below
# is the figure Section V-F now retracts: it came from a single restart
# initialised at autocorrelation 0.85.  Kept for provenance only.
# Do not re-run to produce a figure; see recreate_fig_pgd_corrected.py.
# Generates fig_loadsweep.pdf and fig_pgd.pdf from REAL measured data.
# Style: muted academic palette + Arial (matches paper figures).
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import rcParams

rcParams["font.family"] = "Arial"
rcParams["pdf.fonttype"] = 42
rcParams["axes.linewidth"] = 0.7
rcParams["font.size"] = 8

NAVY="#25405c"; BURG="#8a3a45"; FOREST="#3a6b4a"; MUST="#c08a2e"; SLATE="#5b6b7b"; GRAY="#9aa3ab"
OUT=r"D:\프랑스 업데이트\TNSE 스페셜이슈 논문\IS-Raft-LAC\submission\figures"

# ---------- Figure: load sweep (Table chaingo E1/E2/E3, real in-paper data) ----------
C   = [1,2,4,8,16]
e1  = [2.44,3.21,6.41,12.24,24.44]; e1s=[0.03,0.11,0.11,1.43,1.69]   # clean
e2  = [2.45,3.26,7.88,11.52,24.13]; e2s=[0.06,0.05,1.18,0.51,1.11]   # +200ms attack
e3  = [2.44,3.25,6.31,13.78,25.38]; e3s=[0.01,0.05,0.10,4.18,1.57]   # attack + BORA

fig,ax=plt.subplots(figsize=(3.45,2.25))
x=range(len(C))
ax.errorbar(x,e1,yerr=e1s,marker="o",ms=4,lw=1.4,color=NAVY,capsize=2,label="E1 clean")
ax.errorbar(x,e2,yerr=e2s,marker="s",ms=4,lw=1.4,color=BURG,capsize=2,label="E2 attack ($+200$ ms)")
ax.errorbar(x,e3,yerr=e3s,marker="^",ms=4,lw=1.4,color=FOREST,capsize=2,label="E3 attack$+$BORA")
ax.set_xticks(list(x)); ax.set_xticklabels(C)
ax.set_xlabel("Client concurrency $C$"); ax.set_ylabel("Committed throughput (TPS)")
ax.legend(frameon=False,fontsize=7,loc="upper left")
ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
ax.grid(axis="y",ls=":",lw=0.5,color=GRAY,alpha=0.7)
fig.tight_layout(pad=0.3)
fig.savefig(OUT+r"\fig_loadsweep.pdf"); fig.savefig(OUT+r"\fig_loadsweep.png",dpi=150)
print("loadsweep done")

# ---------- Figure: white-box PGD adaptive adversary (mm_adaptive_results.txt) ----------
rho=[0.0,0.3,0.6,0.8]; auc=[0.774,0.748,0.733,0.819]
NONAD=0.923; CHANCE=0.5; OFF=0.536

fig,ax=plt.subplots(figsize=(3.45,2.25))
ax.axhline(NONAD,ls="--",lw=1.1,color=MUST)
ax.text(0.0,NONAD+0.008,"non-adaptive (0.92)",fontsize=6.5,color=MUST)
ax.axhline(CHANCE,ls=":",lw=1.1,color=GRAY)
ax.text(0.0,CHANCE-0.05,"chance (0.5)",fontsize=6.5,color=GRAY)
ax.plot(rho,auc,marker="o",ms=5,lw=1.7,color=NAVY,label="white-box PGD")
wi=auc.index(min(auc))
ax.annotate("worst case 0.73",xy=(rho[wi],auc[wi]),xytext=(0.40,0.60),
            fontsize=7,color=BURG,
            arrowprops=dict(arrowstyle="-",lw=0.6,color=BURG))
ax.set_ylim(0.42,1.0); ax.set_xlim(-0.04,0.88)
ax.set_xlabel("autocorrelation floor $\\rho_{\\min}$"); ax.set_ylabel("detection AUC")
ax.legend(frameon=False,fontsize=7,loc="lower right")
ax.spines["top"].set_visible(False); ax.spines["right"].set_visible(False)
ax.grid(axis="y",ls=":",lw=0.5,color=GRAY,alpha=0.7)
fig.tight_layout(pad=0.3)
fig.savefig(OUT+r"\fig_pgd.pdf"); fig.savefig(OUT+r"\fig_pgd.png",dpi=150)
print("pgd done")
