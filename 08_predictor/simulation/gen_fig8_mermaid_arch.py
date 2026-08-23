"""
gen_fig8_mermaid_arch.py - Generate architecture figure from user's
mermaid graph TD specification.

Layout (bottom-up):
  Plane 1: Network & Threat  (N1, N2, N3)
  Plane 2: Consensus          (C1, C2, C3)
  Plane 3: Bounded Intelligence (I1->I2->I3->I4->I5->I6 + Thm)
  Plane 4: Deployment         (D1, D2, D3)
  + Coverage strip (right side)
  + Cross-plane arrows (Telemetry, Blacklist, Integration)
"""
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle, FancyArrowPatch
from matplotlib.patches import ConnectionPatch
import numpy as np

fig, ax = plt.subplots(figsize=(14, 10))
ax.set_xlim(0, 14)
ax.set_ylim(0, 12)
ax.axis('off')

# Color palette per plane
C_NET = '#E8F0FE'
C_CON = '#E6F4EA'
C_INT = '#FFF2CC'
C_DEP = '#FCE5CD'
C_COV = '#D9D9D9'
C_THM = '#F4CCCC'
C_BOX = '#1A1A1A'
C_ARROW = '#0080A0'
C_BLACKLIST = '#B7472A'

def box(x, y, w, h, color, label, sub=None, fontsize=9.5, sub_size=7.5):
    r = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.06",
                       linewidth=1.3, edgecolor=C_BOX, facecolor=color)
    ax.add_patch(r)
    if sub:
        ax.text(x + w/2, y + h*0.70, label, ha='center', va='center',
                fontsize=fontsize, fontweight='bold')
        ax.text(x + w/2, y + h*0.30, sub, ha='center', va='center',
                fontsize=sub_size, style='italic', color='#444')
    else:
        ax.text(x + w/2, y + h/2, label, ha='center', va='center',
                fontsize=fontsize, fontweight='bold')

def plane_bg(x, y, w, h, color, plane_label):
    r = Rectangle((x, y), w, h, facecolor=color, edgecolor=C_BOX,
                  linewidth=1.6, alpha=0.5)
    ax.add_patch(r)
    ax.text(x + 0.15, y + h - 0.25, plane_label, ha='left', va='top',
            fontsize=8.5, fontweight='bold', color='#555')

def arrow(x1, y1, x2, y2, color=C_ARROW, lw=1.4, label=None, style='->',
          rad=0.0):
    if rad == 0:
        ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle=style, color=color, lw=lw))
    else:
        ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle=style, color=color, lw=lw,
                                    connectionstyle=f"arc3,rad={rad}"))
    if label:
        ax.text((x1+x2)/2 + 0.1, (y1+y2)/2 + 0.15, label, fontsize=8,
                color=color, fontweight='bold')

def dashed_arrow(x1, y1, x2, y2, color=C_BOX, lw=1.2, label=None):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle='->', color=color, lw=lw,
                                linestyle='dashed'))
    if label:
        ax.text((x1+x2)/2 + 0.1, (y1+y2)/2 + 0.1, label, fontsize=7.5,
                color=color, style='italic')

# ===== Title =====
ax.text(7, 11.55, 'IS-Raft-LAC: System Architecture',
        ha='center', fontsize=14, fontweight='bold')
ax.text(7, 11.2,
        '4 Planes + Bounded Blacklist Advisor + 60-Experiment Coverage',
        ha='center', fontsize=10, style='italic', color='#444')

# ===== Plane 4: Deployment (top) =====
plane_bg(0.3, 9.4, 10.2, 1.4, C_DEP,
         '4. Deployment Plane (Artifacts & Benchmarks)')
box(0.9, 9.55, 2.7, 1.1, '#FFD580', 'D1: Docker / Helm / K8s',
    'OCI + StatefulSet')
box(3.8, 9.55, 2.7, 1.1, '#F4A460', 'D2: Terraform AWS',
    '3 regions, EC2')
box(6.7, 9.55, 3.6, 1.1, '#E69138', 'D3: Fabric+Caliper Bench.',
    '3 workloads, 30-min steady')

# ===== Plane 3: Bounded Intelligence =====
plane_bg(0.3, 6.6, 10.2, 2.55, C_INT,
         '3. Bounded Intelligence Plane (Algorithm 1)')

# I1->I2->I3->I4->I5->I6 in a horizontal chain
nodes_I = [
    ('I1: Observer',     '24-ch telemetry'),
    ('I2: Predictor',    'AR(1) Memory-enabled'),
    ('I3: PATE DP',      'Ensemble of K=10'),
    ('I4: ACI',          'Conformal calibration'),
    ('I5: Advisor',      'Algorithm 1'),
    ('I6: Bounded $\\mathcal{B}_t$', '$|\\mathcal{B}_t| < f$'),
]
xs_I = np.linspace(0.6, 9.0, 6)
y_I = 7.2
w_I = 1.42
h_I = 1.0
for i, (lbl, sub) in enumerate(nodes_I):
    color = '#FFE699' if i < 4 else '#F4D060' if i == 4 else '#E69138'
    box(xs_I[i], y_I, w_I, h_I, color, lbl, sub, fontsize=9, sub_size=7)
    if i < 5:
        # arrow to next
        arrow(xs_I[i] + w_I + 0.02, y_I + h_I/2,
              xs_I[i+1] - 0.02, y_I + h_I/2,
              color=C_BOX, lw=1.3)

# 7 Theorems tag (dashed to I2)
box(0.6, 8.4, 2.4, 0.5, C_THM,
    '7 Theorems: Impossibility Bounds', fontsize=8.5)
dashed_arrow(1.8, 8.4, xs_I[1] + w_I/2, y_I + h_I)

# Output annotation
ax.text(xs_I[5] + w_I/2, y_I - 0.15,
        'Outputs to Consensus', fontsize=7.5, color=C_BLACKLIST,
        ha='center', style='italic')

# ===== Plane 2: Consensus =====
plane_bg(0.3, 4.6, 10.2, 1.7, C_CON,
         '2. Consensus Plane (Safety & Liveness)')

box(0.9, 5.0, 3.0, 1.1, '#B7E1CD', 'C1: Raft / Fabric',
    'Vanilla unmodified')
box(4.1, 5.0, 3.0, 1.1, '#93C47D', 'C2: Active-Leader Rule',
    'v12+RD4 verified')
box(7.3, 5.0, 3.0, 1.1, '#93C47D', 'C3: $K_{fail}$ Fail-Open',
    'Liveness fallback')

# C1 -- C2 -- C3 connections (undirected)
ax.plot([3.9, 4.1], [5.55, 5.55], color=C_BOX, lw=1.5)
ax.plot([7.1, 7.3], [5.55, 5.55], color=C_BOX, lw=1.5)

# ===== Plane 1: Network & Threat (bottom) =====
plane_bg(0.3, 1.9, 10.2, 2.3, C_NET,
         '1. Network & Threat Plane')

box(0.9, 2.45, 3.0, 1.3, '#A4C2F4', 'N1: Multi-AZ / RD3',
    '3 regions × 2 AZ')
box(4.1, 2.45, 3.0, 1.3, '#6FA8DC', 'N2: Telemetry Window',
    'CC, RTT, AR(1)')
box(7.3, 2.45, 3.0, 1.3, '#A4C2F4', 'N3: Byzantine Threat',
    'Moment-match, Burst, Lag')

# N3 -.-> N1 (dashed)
dashed_arrow(8.8, 2.45, 2.4, 2.45 + 0.15, color='#B7472A')
# N1 --> N2
arrow(3.9, 3.1, 4.1, 3.1, color=C_BOX, lw=1.5)

# ===== Cross-plane arrows =====
# Network -> Intelligence (Telemetry data X)
arrow(5.5, 4.2, 5.5, 6.6, color=C_ARROW, lw=2.2, rad=0.0)
ax.text(5.65, 5.4, 'Telemetry Data $X$', fontsize=9, color=C_ARROW,
        fontweight='bold', rotation=90, va='center')

# Intelligence -> Consensus (Blacklist B_t)
arrow(xs_I[5] + w_I/2, y_I, xs_I[5] + w_I/2, 6.15,
      color=C_BLACKLIST, lw=2.2)
ax.text(xs_I[5] + w_I/2 + 0.15, 6.45,
        'Blacklist $\\mathcal{B}_t$', fontsize=9, color=C_BLACKLIST,
        fontweight='bold')

# Consensus -> Deployment (Integration)
arrow(5.5, 6.1, 5.5, 9.4, color='#666', lw=1.6, rad=0.15)
ax.text(5.95, 7.75, 'Integration', fontsize=8.5, color='#666',
        rotation=90, va='center', style='italic')

# ===== Coverage Strip (right side) =====
plane_bg(11.0, 1.9, 2.7, 8.9, C_COV,
         '60 Experiments Coverage Strip')

cov_items = [
    ('RQ1--RQ5', 'Hybrid eval'),
    ('E1--E6', 'Theoretical'),
    ('L1--O1', '4-round panel'),
    ('NW1--NW5', 'Weakness mit.'),
    ('FX1--FX5', 'Fixes + v15 ACI'),
    ('NE1--NE5', 'Panel + PATE'),
    ('RD1--RD4', 'Real wall-clock'),
    ('U4 Fabric', '3 workloads × 30min'),
    ('T7 + T6-FORMAL', 'v14--v16 theorems'),
]
y_cov_start = 9.6
y_cov_step = 0.85
for i, (lbl, sub) in enumerate(cov_items):
    y_c = y_cov_start - i * y_cov_step
    box(11.2, y_c, 2.3, 0.7, '#B0B0B0', lbl, sub,
        fontsize=8.5, sub_size=6.5)

# ===== Bottom verification chain =====
ax.text(5.5, 1.45,
        '173,200+ simulated  +  30s + 135s + RD3 + RD4 wall-clock '
        '+ $9{\\times}30$min Fabric  =  $\\mathbf{0}$ safety violations across all',
        ha='center', fontsize=9, fontweight='bold', color='#0B5345',
        bbox=dict(facecolor='#D9F0E0', edgecolor='#0B5345',
                  boxstyle='round,pad=0.4'))

# Bottom-right credit
ax.text(13.6, 0.4, 'v16 (submission16)', fontsize=7.5, color='#888',
        ha='right', style='italic')

plt.tight_layout()
plt.savefig('figures/fig8_mermaid_architecture.pdf', dpi=300,
            bbox_inches='tight')
plt.savefig('figures/fig8_mermaid_architecture.png', dpi=200,
            bbox_inches='tight')
print('Saved figures/fig8_mermaid_architecture.{pdf,png}')
