"""
gen_fig6_architecture.py - Generate best-in-class architecture figure
for v12 (submission12) of TNSE special issue paper.

Layout (4-plane stacked + experiment coverage strip):
  +-------------------------------------------------------------+
  |  PLANE 4: Deployment       [Docker | Helm | Terraform | K8s] |
  +-------------------------------------------------------------+
  |  PLANE 3: Intelligence     [Observer -> Predictor -> Advisor]|
  +-------------------------------------------------------------+
  |  PLANE 2: Consensus Safety [Election | Log | Quorum]         |
  +-------------------------------------------------------------+
  |  PLANE 1: Network          [Telemetry (CC, RTT) + WAN]       |
  +-------------------------------------------------------------+
  |  46 Experiments Coverage   [S1-S3|R|NW|FX|D|RD1|RD2]         |
  +-------------------------------------------------------------+
"""
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle
import numpy as np

fig, ax = plt.subplots(figsize=(12, 8))
ax.set_xlim(0, 12)
ax.set_ylim(0, 11)
ax.axis('off')

# Color palette
C_NET = '#E8F0FE'      # Plane 1 network (blue tint)
C_CON = '#E6F4EA'      # Plane 2 consensus (green tint)
C_AI = '#FFF2CC'       # Plane 3 intelligence (yellow tint)
C_DEP = '#FCE5CD'      # Plane 4 deployment (orange tint)
C_EXP = '#D9D9D9'      # Experiment coverage (gray)
C_BOX = '#1A1A1A'
C_THM = '#C00000'      # Theorem connection lines (red)

def box(x, y, w, h, color, label, sub=None):
    r = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05",
                       linewidth=1.2, edgecolor=C_BOX, facecolor=color)
    ax.add_patch(r)
    ax.text(x + w/2, y + h*0.65, label, ha='center', va='center',
            fontsize=9.5, fontweight='bold')
    if sub:
        ax.text(x + w/2, y + h*0.25, sub, ha='center', va='center',
                fontsize=7.5, style='italic')

def arrow(x1, y1, x2, y2, color=C_BOX, style='->', lw=1.0):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle=style, color=color, lw=lw))

# ----- Title -----
ax.text(6, 10.6, 'Provably Safe Predictive Augmentation: System Architecture',
        ha='center', fontsize=13, fontweight='bold')
ax.text(6, 10.2, '4-Plane stratification + 46-experiment empirical coverage',
        ha='center', fontsize=9.5, style='italic', color='#444')

# ===== PLANE 4: Deployment =====
ax.add_patch(Rectangle((0.3, 8.4), 11.4, 1.4, facecolor=C_DEP,
                        edgecolor=C_BOX, lw=1.5))
ax.text(0.6, 9.5, 'Plane 4', fontsize=8, color='#666', fontweight='bold')
ax.text(0.6, 9.2, 'Deployment', fontsize=8, color='#666')
box(2.1, 8.6, 1.7, 1.0, '#FFD580', 'Docker', 'OCI container')
box(4.0, 8.6, 1.7, 1.0, '#FFD580', 'Helm', 'K8s chart')
box(5.9, 8.6, 1.9, 1.0, '#F4A460', 'Terraform', 'AWS 3-region')
box(8.0, 8.6, 1.9, 1.0, '#F4A460', 'K8s multi-cluster', 'Kubefed manifest')
ax.text(10.4, 9.1, 'RD1 / RD2', fontsize=8.5, fontweight='bold', color='#B7472A')

# ===== PLANE 3: Intelligence =====
ax.add_patch(Rectangle((0.3, 6.6), 11.4, 1.6, facecolor=C_AI,
                        edgecolor=C_BOX, lw=1.5))
ax.text(0.6, 7.9, 'Plane 3', fontsize=8, color='#666', fontweight='bold')
ax.text(0.6, 7.6, 'Bounded', fontsize=8, color='#666')
ax.text(0.6, 7.3, 'Intelligence', fontsize=8, color='#666')

box(2.1, 6.85, 1.8, 1.1, '#FFE699', 'Observer', '24-ch telemetry')
box(4.1, 6.85, 1.8, 1.1, '#FFE699', 'Predictor', 'MLP/LSTM/Tx')
box(6.1, 6.85, 1.8, 1.1, '#FFE699', 'Advisor', 'Algorithm 1')
box(8.1, 6.85, 1.8, 1.1, '#F4D060', 'Calibrator', 'Platt + Conformal')

# Theorem connections
ax.text(10.4, 7.7, 'Thm 1-4', fontsize=9, fontweight='bold', color=C_THM)
ax.text(10.4, 7.4, 'Impossibility', fontsize=7.5, color=C_THM)
ax.text(10.4, 7.15, '+ extensions', fontsize=7.5, color=C_THM)
ax.text(10.4, 6.9, '(NW3/NW4)', fontsize=7.5, color=C_THM)

# Observer -> Predictor -> Advisor flow
arrow(3.9, 7.4, 4.1, 7.4, lw=1.3)
arrow(5.9, 7.4, 6.1, 7.4, lw=1.3)
arrow(7.9, 7.4, 8.1, 7.4, lw=1.3)

# ===== PLANE 2: Consensus Safety =====
ax.add_patch(Rectangle((0.3, 4.8), 11.4, 1.6, facecolor=C_CON,
                        edgecolor=C_BOX, lw=1.5))
ax.text(0.6, 6.1, 'Plane 2', fontsize=8, color='#666', fontweight='bold')
ax.text(0.6, 5.8, 'Consensus', fontsize=8, color='#666')
ax.text(0.6, 5.5, 'Safety', fontsize=8, color='#666')

box(2.1, 5.05, 1.8, 1.1, '#B7E1CD', 'Election Safety', '$\\leq 1$ leader/term')
box(4.1, 5.05, 1.8, 1.1, '#B7E1CD', 'Log Matching', 'append-only')
box(6.1, 5.05, 1.8, 1.1, '#B7E1CD', 'Quorum $\\geq \\lceil n/2 \\rceil+1$', 'unchanged')
box(8.1, 5.05, 1.8, 1.1, '#93C47D', 'Fail-Open', '$K_{fail}$-step')

ax.text(10.4, 5.7, 'Thm 5+6', fontsize=9, fontweight='bold', color=C_THM)
ax.text(10.4, 5.4, 'Augmentation', fontsize=7.5, color=C_THM)
ax.text(10.4, 5.15, 'Safety', fontsize=7.5, color=C_THM)

# ===== PLANE 1: Network =====
ax.add_patch(Rectangle((0.3, 3.0), 11.4, 1.6, facecolor=C_NET,
                        edgecolor=C_BOX, lw=1.5))
ax.text(0.6, 4.3, 'Plane 1', fontsize=8, color='#666', fontweight='bold')
ax.text(0.6, 4.0, 'Network', fontsize=8, color='#666')
ax.text(0.6, 3.7, 'Telemetry', fontsize=8, color='#666')

box(2.1, 3.25, 1.8, 1.1, '#A4C2F4', 'CC channel', 'compute cost')
box(4.1, 3.25, 1.8, 1.1, '#A4C2F4', 'RTT channel', 'round-trip')
box(6.1, 3.25, 1.8, 1.1, '#A4C2F4', 'AR(1) state', 'autocorrelation')
box(8.1, 3.25, 1.8, 1.1, '#6FA8DC', 'WAN: 3 regions', '80/150/220 ms')

# ===== Inter-plane connections (data flow upward) =====
arrow(3.0, 4.35, 3.0, 4.8, color='#0080A0', lw=1.5)
arrow(3.0, 6.4, 3.0, 6.85, color='#0080A0', lw=1.5)
arrow(7.0, 6.4, 7.0, 6.85, color='#0080A0', lw=1.5)

# Advisor -> Consensus (downward blacklist injection)
arrow(7.0, 6.85, 7.0, 6.15, color='#B7472A', lw=1.7, style='->')
ax.text(7.2, 6.5, r'$\mathcal{B}_t$', fontsize=10, color='#B7472A', fontweight='bold')

# ===== EXPERIMENT COVERAGE STRIP =====
ax.add_patch(Rectangle((0.3, 1.2), 11.4, 1.5, facecolor=C_EXP,
                        edgecolor=C_BOX, lw=1.5))
ax.text(0.6, 2.4, '46 Experiments', fontsize=8.5, color='#333', fontweight='bold')
ax.text(0.6, 2.1, 'Coverage', fontsize=8.5, color='#333')
ax.text(0.6, 1.8, 'Map', fontsize=8.5, color='#333')

exp_groups = [
    ('S1-S3', '23 exp', '#9FC5E8', 'Stage 1-3'),
    ('R1-R4', '8 exp',  '#A2C4C9', 'Rounds A/B'),
    ('NW1-5', '5 exp',  '#FFD966', 'Weakness mit.'),
    ('FX1-5', '5 exp',  '#F6B26B', 'Fixes'),
    ('D2-D4', '3 exp',  '#E06666', 'Emul (HF/NS/MTS)'),
    ('RD1',   '1 exp',  '#93C47D', 'Real wall-clock'),
    ('RD2',   '1 exp',  '#76A5AF', 'Multi-region'),
]
x0 = 2.1
w = 1.32
gap = 0.05
for i, (lbl, cnt, col, desc) in enumerate(exp_groups):
    xx = x0 + i*(w + gap)
    box(xx, 1.35, w, 1.2, col, lbl, cnt)
    ax.text(xx + w/2, 1.05, desc, ha='center', fontsize=6.5, style='italic')

# ===== Bottom: Verification chain =====
ax.text(6, 0.55,
        '173,200+ simulated events  +  30s single-host wall-clock  +  135s multi-region wall-clock  =  0 safety violations',
        ha='center', fontsize=9, fontweight='bold', color='#0B5345',
        bbox=dict(facecolor='#D9F0E0', edgecolor='#0B5345', boxstyle='round,pad=0.4'))

plt.tight_layout()
plt.savefig('figures/fig6_architecture.pdf', dpi=300, bbox_inches='tight')
plt.savefig('figures/fig6_architecture.png', dpi=200, bbox_inches='tight')
print('Saved figures/fig6_architecture.{pdf,png}')
