"""
gen_fig7_architecture_v16.py - Updated architecture figure for v16.

Adds v14/v15 contributions to the v12 Figure 6 layout:
  - PATE-style DP (NE2-EXT) in Intelligence plane
  - ACI (FX5-EXT) in Intelligence plane
  - RD4 partition+blacklist in Deployment plane
  - 60+ experiment coverage strip update
"""
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle
import numpy as np

fig, ax = plt.subplots(figsize=(12, 8.5))
ax.set_xlim(0, 12)
ax.set_ylim(0, 11.5)
ax.axis('off')

C_NET = '#E8F0FE'
C_CON = '#E6F4EA'
C_AI = '#FFF2CC'
C_DEP = '#FCE5CD'
C_EXP = '#D9D9D9'
C_BOX = '#1A1A1A'
C_THM = '#C00000'


def box(x, y, w, h, color, label, sub=None):
    r = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05",
                       linewidth=1.2, edgecolor=C_BOX, facecolor=color)
    ax.add_patch(r)
    ax.text(x + w/2, y + h*0.65, label, ha='center', va='center',
            fontsize=9.5, fontweight='bold')
    if sub:
        ax.text(x + w/2, y + h*0.25, sub, ha='center', va='center',
                fontsize=7.0, style='italic')


def arrow(x1, y1, x2, y2, color=C_BOX, lw=1.0):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle='->', color=color, lw=lw))


ax.text(6, 11.1, 'v16 Architecture: 4-Plane + 60-Experiment Coverage',
        ha='center', fontsize=13, fontweight='bold')
ax.text(6, 10.75, '7 theorems + RD1-RD4 + PATE + ACI + Fabric+Caliper',
        ha='center', fontsize=9.5, style='italic', color='#444')

# PLANE 4: Deployment
ax.add_patch(Rectangle((0.3, 8.9), 11.4, 1.4, facecolor=C_DEP,
                       edgecolor=C_BOX, lw=1.5))
ax.text(0.6, 10.0, 'Plane 4', fontsize=8, color='#666', fontweight='bold')
ax.text(0.6, 9.7, 'Deployment', fontsize=8, color='#666')
box(2.1, 9.1, 1.5, 1.0, '#FFD580', 'Docker', 'OCI')
box(3.7, 9.1, 1.5, 1.0, '#FFD580', 'Helm', 'K8s chart')
box(5.3, 9.1, 1.7, 1.0, '#F4A460', 'Terraform', 'AWS 3-region')
box(7.1, 9.1, 1.7, 1.0, '#F4A460', 'K8s multi-cluster', 'Kubefed')
box(8.9, 9.1, 1.7, 1.0, '#F4A460', 'Fabric+Caliper', 'U4 3 workloads')
ax.text(10.7, 9.6, 'RD1-RD4', fontsize=8.5, fontweight='bold', color='#B7472A')

# PLANE 3: Intelligence
ax.add_patch(Rectangle((0.3, 7.0), 11.4, 1.7, facecolor=C_AI,
                       edgecolor=C_BOX, lw=1.5))
ax.text(0.6, 8.3, 'Plane 3', fontsize=8, color='#666', fontweight='bold')
ax.text(0.6, 8.0, 'Bounded', fontsize=8, color='#666')
ax.text(0.6, 7.7, 'Intelligence', fontsize=8, color='#666')

box(2.1, 7.2, 1.6, 1.2, '#FFE699', 'Observer', '24-ch telemetry')
box(3.8, 7.2, 1.6, 1.2, '#FFE699', 'Predictor', 'MLP/LSTM/Tx')
box(5.5, 7.2, 1.6, 1.2, '#FFE699', 'Advisor', 'Algorithm 1')
box(7.2, 7.2, 1.6, 1.2, '#F4D060', 'PATE+ACI', 'NE2/FX5-EXT')
box(8.9, 7.2, 1.6, 1.2, '#F4D060', 'Calibrator', 'Platt + CP')

ax.text(10.7, 8.1, 'Thm 1-4,7', fontsize=8.5, fontweight='bold', color=C_THM)
ax.text(10.7, 7.85, 'Impossibility', fontsize=7.5, color=C_THM)
ax.text(10.7, 7.6, '+ Approx', fontsize=7.5, color=C_THM)
ax.text(10.7, 7.35, '(T7 v14)', fontsize=7.5, color=C_THM)

# Observer -> Predictor -> Advisor flow
arrow(3.7, 7.7, 3.8, 7.7, lw=1.3)
arrow(5.4, 7.7, 5.5, 7.7, lw=1.3)
arrow(7.1, 7.7, 7.2, 7.7, lw=1.3)
arrow(8.8, 7.7, 8.9, 7.7, lw=1.3)

# PLANE 2: Consensus Safety
ax.add_patch(Rectangle((0.3, 5.0), 11.4, 1.7, facecolor=C_CON,
                       edgecolor=C_BOX, lw=1.5))
ax.text(0.6, 6.3, 'Plane 2', fontsize=8, color='#666', fontweight='bold')
ax.text(0.6, 6.0, 'Consensus', fontsize=8, color='#666')
ax.text(0.6, 5.7, 'Safety', fontsize=8, color='#666')

box(2.1, 5.2, 1.6, 1.2, '#B7E1CD', 'Election Safety', '$\\leq 1$ leader/term')
box(3.8, 5.2, 1.6, 1.2, '#B7E1CD', 'Log Matching', 'append-only')
box(5.5, 5.2, 1.6, 1.2, '#B7E1CD', 'Quorum', 'unchanged')
box(7.2, 5.2, 1.6, 1.2, '#93C47D', 'Fail-Open', '$K_{fail}$ step')
box(8.9, 5.2, 1.6, 1.2, '#93C47D', 'Active-Ldr Rule', 'v12+RD4 verif.')

ax.text(10.7, 6.1, 'Thm 5+6', fontsize=8.5, fontweight='bold', color=C_THM)
ax.text(10.7, 5.85, 'Augmentation', fontsize=7.5, color=C_THM)
ax.text(10.7, 5.6, 'Safety', fontsize=7.5, color=C_THM)

# Advisor -> Consensus (blacklist injection)
arrow(8.0, 7.2, 8.0, 6.4, color='#B7472A', lw=1.7)
ax.text(8.2, 6.8, r'$\mathcal{B}_t$', fontsize=10, color='#B7472A',
        fontweight='bold')

# PLANE 1: Network
ax.add_patch(Rectangle((0.3, 3.0), 11.4, 1.7, facecolor=C_NET,
                       edgecolor=C_BOX, lw=1.5))
ax.text(0.6, 4.3, 'Plane 1', fontsize=8, color='#666', fontweight='bold')
ax.text(0.6, 4.0, 'Network', fontsize=8, color='#666')
ax.text(0.6, 3.7, 'Telemetry', fontsize=8, color='#666')

box(2.1, 3.2, 1.6, 1.2, '#A4C2F4', 'CC channel', 'compute cost')
box(3.8, 3.2, 1.6, 1.2, '#A4C2F4', 'RTT channel', 'round-trip')
box(5.5, 3.2, 1.6, 1.2, '#A4C2F4', 'AR(1) state', 'autocorrelation')
box(7.2, 3.2, 1.6, 1.2, '#6FA8DC', 'WAN: 3 regions', '80/150/220 ms')
box(8.9, 3.2, 1.6, 1.2, '#6FA8DC', 'Multi-AZ', '$\\pm 10\\%$ asym (RD3)')

# Plane 1 -> Plane 3 (telemetry flow upward)
arrow(3.0, 4.4, 3.0, 7.2, color='#0080A0', lw=1.5)

# Experiment coverage strip
ax.add_patch(Rectangle((0.3, 1.0), 11.4, 1.6, facecolor=C_EXP,
                       edgecolor=C_BOX, lw=1.5))
ax.text(0.6, 2.2, '60 Experiments', fontsize=8.5, color='#333', fontweight='bold')
ax.text(0.6, 1.9, 'Coverage', fontsize=8.5, color='#333')
ax.text(0.6, 1.6, '(v16)', fontsize=8.5, color='#333')

exp_groups = [
    ('S1-S3', '23 exp', '#9FC5E8', 'Stage 1-3'),
    ('R1-R4', '8 exp', '#A2C4C9', 'Rounds A/B'),
    ('NW1-5', '5 exp', '#FFD966', 'Weakness mit.'),
    ('FX1-5+ACI', '6 exp', '#F6B26B', 'Fixes + v15'),
    ('NE1-5+PATE', '7 exp', '#E06666', 'Panel + v15+v16'),
    ('D2-D4', '3 exp', '#76A5AF', 'Emul'),
    ('RD1-RD4+U4', '7 exp', '#93C47D', 'Real depl.'),
    ('T6-FORMAL', '1 exp', '#B4A7D6', 'v16 joint'),
]
x0 = 2.1
w = 1.15
gap = 0.04
for i, (lbl, cnt, col, desc) in enumerate(exp_groups):
    xx = x0 + i*(w + gap)
    box(xx, 1.15, w, 1.2, col, lbl, cnt)
    ax.text(xx + w/2, 0.85, desc, ha='center', fontsize=6, style='italic')

# Verification chain
ax.text(6, 0.45,
        '173,200+ simulated  +  30s + 135s + RD3 + RD4 wall-clock '
        '+ $9{\\times}30$min Fabric  =  0 safety violations across all',
        ha='center', fontsize=8.5, fontweight='bold', color='#0B5345',
        bbox=dict(facecolor='#D9F0E0', edgecolor='#0B5345',
                  boxstyle='round,pad=0.4'))

plt.tight_layout()
plt.savefig('figures/fig7_architecture_v16.pdf', dpi=300, bbox_inches='tight')
plt.savefig('figures/fig7_architecture_v16.png', dpi=200, bbox_inches='tight')
print('Saved figures/fig7_architecture_v16.{pdf,png}')
