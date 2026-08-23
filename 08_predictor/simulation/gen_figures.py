"""
gen_figures.py — Generate 4 key figures for v28 manuscript.

  Figure 1: Consistency-Robustness curve (Stage 2C)
  Figure 2: Theorem 1 phase transition (E1 + C1)
  Figure 3: Theorem 4 tightness (E2 + extended)
  Figure 4: Stage 3 TPS-Latency (R3A)
"""

from pathlib import Path
import math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = Path(__file__).parent / "figures"
OUT.mkdir(exist_ok=True)

plt.rcParams.update({
    "font.size": 9,
    "axes.titlesize": 10,
    "axes.labelsize": 9,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "legend.fontsize": 8,
    "figure.dpi": 150,
})


# ---------------------------------------------------------------------------
# Figure 1: Consistency-Robustness Curve
# ---------------------------------------------------------------------------

fig, ax1 = plt.subplots(figsize=(4.2, 2.8))
pred_auc = np.array([0.00, 0.20, 0.50, 0.80, 0.95, 1.00])
gain_pct = np.array([0.0, 0.0, 0.0, 36.0, 54.0, 60.0])
safety_viol = np.array([0, 0, 0, 0, 0, 0])

ax1.plot(pred_auc, gain_pct, 'o-', color='steelblue', linewidth=2,
         label='System gain (%)', markersize=6)
ax1.axvline(x=0.5, color='gray', linestyle='--', alpha=0.5)
ax1.fill_between([0.0, 0.5], -5, 70, color='lightcoral', alpha=0.15,
                 label='Fail-open region')
ax1.fill_between([0.5, 1.0], -5, 70, color='lightgreen', alpha=0.15,
                 label='Consistency region')
ax1.set_xlabel(r'Predictor AUC')
ax1.set_ylabel(r'Failover gain (\%)', color='steelblue')
ax1.tick_params(axis='y', labelcolor='steelblue')
ax1.set_ylim(-5, 70)
ax1.set_title(r'Consistency--Robustness Profile (Stage 2C)')
ax1.grid(alpha=0.3)

ax2 = ax1.twinx()
ax2.bar(pred_auc, np.maximum(safety_viol, 0.05), width=0.04, color='darkred',
        alpha=0.5, label='Safety violations')
ax2.set_ylabel(r'Safety violations', color='darkred')
ax2.tick_params(axis='y', labelcolor='darkred')
ax2.set_ylim(0, 5)

ax1.legend(loc='upper left', fontsize=7)
plt.tight_layout()
plt.savefig(OUT / "fig1_consistency_robustness.pdf", bbox_inches='tight')
plt.close()
print(f"Wrote: {OUT}/fig1_consistency_robustness.pdf")


# ---------------------------------------------------------------------------
# Figure 2: Theorem 1 Phase Transition (E1 + C1)
# ---------------------------------------------------------------------------

fig, ax = plt.subplots(figsize=(4.2, 2.8))
delta = np.array([0.00, 0.02, 0.04, 0.06, 0.08, 0.10, 0.15, 0.20, 0.30, 0.50, 0.75, 1.00])
empirical = np.array([0.573, 0.573, 0.574, 0.574, 0.575, 0.575, 0.576, 0.577, 0.580, 0.588, 0.602, 0.620])
theory = np.array([0.5 * (1 + math.erf(d/2.0)) for d in delta])

ax.plot(delta, empirical, 's-', color='crimson', linewidth=1.8,
        label='Empirical (linear scorer)', markersize=5)
ax.plot(delta, theory, '^--', color='darkblue', linewidth=1.8,
        label=r'Theory $\Phi(\delta/\sqrt{2})$', markersize=5)
ax.axhline(y=0.5, color='gray', linestyle=':', alpha=0.7,
           label=r'Thm 1 ceiling (AUC$=1/2$)')

ax.set_xlabel(r'Moment-matching slack $\delta$ ($\sigma$ units)')
ax.set_ylabel(r'Detection AUC')
ax.set_title(r'Theorem 1 Phase Transition (E1 + C1)')
ax.legend(loc='lower right', fontsize=8)
ax.set_ylim(0.45, 0.85)
ax.grid(alpha=0.3)
plt.tight_layout()
plt.savefig(OUT / "fig2_theorem1_phase.pdf", bbox_inches='tight')
plt.close()
print(f"Wrote: {OUT}/fig2_theorem1_phase.pdf")


# ---------------------------------------------------------------------------
# Figure 3: Theorem 4 Tightness (E2)
# ---------------------------------------------------------------------------

fig, ax = plt.subplots(figsize=(4.2, 2.8))
rho = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95])
empirical_gap = np.array([0.010, 0.042, 0.100, 0.193, 0.338, 0.571, 0.976, 1.809, 4.355, 9.517])
theory_gap = rho**2 / (1 - rho**2)

ax.plot(rho, empirical_gap, 'o-', color='crimson', linewidth=1.8,
        label='Empirical gap', markersize=6)
ax.plot(rho, theory_gap, '^--', color='darkblue', linewidth=1.8,
        label=r'Theory $\rho^2\sigma^2/(1-\rho^2)$', markersize=6)
ax.set_xlabel(r'AR(1) coefficient $\rho_{AR}$')
ax.set_ylabel(r'MSE gap')
ax.set_yscale('log')
ax.set_title(r'Theorem 4 Tightness (E2): Empirical/Theory $\approx 1.02$')
ax.legend(loc='upper left', fontsize=8)
ax.grid(alpha=0.3, which='both')
plt.tight_layout()
plt.savefig(OUT / "fig3_theorem4_tightness.pdf", bbox_inches='tight')
plt.close()
print(f"Wrote: {OUT}/fig3_theorem4_tightness.pdf")


# ---------------------------------------------------------------------------
# Figure 4: Stage 3 TPS-Latency (R3A — realistic 3-phase BFT)
# ---------------------------------------------------------------------------

fig, ax = plt.subplots(figsize=(4.2, 2.8))
tps = np.array([100, 500, 1000, 1500, 2000])
p99_van = np.array([13.92, 13.92, 13.92, 13.92, 18.56])
p99_ai = np.array([12.71, 12.71, 12.71, 12.71, 16.94])
p99_bft = np.array([31.23, 31.23, 31.23, 31.23, 41.64])

ax.plot(tps, p99_van, 'o-', color='steelblue', linewidth=1.8,
        label='Vanilla Raft', markersize=6)
ax.plot(tps, p99_ai, 's-', color='forestgreen', linewidth=1.8,
        label='AI-Augmented Raft', markersize=6)
ax.plot(tps, p99_bft, '^-', color='crimson', linewidth=1.8,
        label='SmartBFT (3-phase)', markersize=6)
ax.set_xlabel(r'Workload (TPS)')
ax.set_ylabel(r'$p99$ latency (ms)')
ax.set_title(r'Stage 3 TPS--Latency at $p99$ (R3A)')
ax.legend(loc='upper left', fontsize=8)
ax.grid(alpha=0.3)
plt.tight_layout()
plt.savefig(OUT / "fig4_tps_latency.pdf", bbox_inches='tight')
plt.close()
print(f"Wrote: {OUT}/fig4_tps_latency.pdf")

print("\n4 figures generated.")
