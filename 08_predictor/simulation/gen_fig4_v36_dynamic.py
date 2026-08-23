"""
gen_fig4_v36_dynamic.py — Dynamic 2D-isometric (faux-3D)
architecture diagram for Fig 4 (4-plane system).

Each plane is drawn as a tilted parallelogram (isometric projection)
with horizontal text inside, gradient fills, drop shadows, and
inter-plane arrows. This keeps text readable while delivering 3D
visual depth.

Layers (bottom to top):
  Plane 1 (Network) — telemetry source
  Plane 2 (Consensus, Pi) — base protocol invariants
  Plane 3 (Bounded Intelligence) — Observer / Predictor / Advisor
  Plane 4 (Deployment) — Fabric + Caliper / RD1-RD4
"""
from __future__ import annotations
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, FancyBboxPatch, FancyArrow
from matplotlib.patches import PathPatch
from matplotlib.path import Path as MPath
from pathlib import Path

OUT = Path(__file__).resolve().parents[2] / "figures"
OUT.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 8.5,
    "axes.titlesize": 9,
    "axes.labelsize": 8,
    "savefig.dpi": 300,
    "figure.dpi": 150,
})

# Isometric tilt (shear) per unit Z
DX, DY = 1.4, 2.3  # how much each upper plane shifts up-right
PW, PH = 13.5, 2.2  # base plane width/height

# Plane spec: z-level, label, fill1 (gradient start), fill2
# (gradient end), edge, components list (text + colored chip)
PLANES = [
    {
        "z": 0,
        "label": "[1] Network Plane",
        "fill": ["#fff8d6", "#ffe2a0"],
        "edge": "#bf8f00",
        "tag_color": "#bf8f00",
        "comps": [
            ("Normal traffic", "#fffbea"),
            ("Packet loss", "#fff3c8"),
            ("WAN asym. (RD3)", "#ffe2a0"),
            ("Byz. telemetry", "#ffcf66"),
        ],
        "theorems": "Threat surfaces & adversaries"
    },
    {
        "z": 1,
        "label": r"[2] Consensus Plane ($\Pi$)",
        "fill": ["#e9f5e0", "#bfe2a4"],
        "edge": "#385723",
        "tag_color": "#385723",
        "comps": [
            ("Election Safety", "#f3faec"),
            ("Log Matching", "#e2f1d0"),
            ("Leader Compl.", "#bfe2a4"),
            ("Active-Leader", "#8fcc6a"),
        ],
        "theorems": "T2 (App. B): static regret"
    },
    {
        "z": 2,
        "label": "[3] Bounded Intelligence Plane",
        "fill": ["#e7f1fb", "#9dc4ec"],
        "edge": "#1f4e79",
        "tag_color": "#1f4e79",
        "comps": [
            ("Observer", "#f0f6fc"),
            ("Predictor (TRF)", "#cce0f4"),
            ("Advisor (Alg. 1)", "#9dc4ec"),
            (r"Fail-Open ($K_{fail}{=}3$)", "#6ba5dc"),
        ],
        "theorems": "T1, T3, T4, T6, T7 (App. A-G): bounds"
    },
    {
        "z": 3,
        "label": "[4] Deployment Plane",
        "fill": ["#fdeede", "#f7b481"],
        "edge": "#c55a11",
        "tag_color": "#c55a11",
        "comps": [
            ("Fabric+Caliper", "#fef4ea"),
            ("RD1-RD4", "#fbd4b4"),
            ("Helm / Terraform", "#f7b481"),
            (r"$30$-min bench", "#ed8c4a"),
        ],
        "theorems": "T5 (App. D): Augmentation Safety"
    },
]


def iso_xy(x, y, z):
    """Convert (logical x, y, z) to 2D screen coords."""
    return x + z * DX, y + z * DY


def draw_iso_plane(ax, z, x0, y0, fill_colors, edge, alpha=0.92):
    """Draw a tilted parallelogram representing a plane at level z."""
    # Plane corners (bottom-left, bottom-right, top-right, top-left)
    p1 = iso_xy(x0, y0, z)
    p2 = iso_xy(x0 + PW, y0, z)
    p3 = iso_xy(x0 + PW, y0 + PH, z)
    p4 = iso_xy(x0, y0 + PH, z)
    pts = np.array([p1, p2, p3, p4])
    # Drop shadow (offset slightly)
    sh_pts = pts + np.array([0.10, -0.10])
    shadow = Polygon(sh_pts, closed=True, facecolor="#000000",
                     edgecolor="none", alpha=0.10, zorder=z*10)
    ax.add_patch(shadow)
    # Gradient fill: render plane as 2 trapezoids vertically split
    # for a simple 2-tone gradient effect (top->bottom)
    mid_y = (p1[1] + p4[1]) / 2
    mid_left = (p1[0], mid_y)
    mid_right = (p2[0], mid_y)
    # Lower half (darker tone of fill_colors[1])
    lower = np.array([p1, p2, mid_right, mid_left])
    upper = np.array([mid_left, mid_right, p3, p4])
    lower_poly = Polygon(lower, closed=True,
                         facecolor=fill_colors[1],
                         edgecolor="none", alpha=alpha,
                         zorder=z*10 + 1)
    upper_poly = Polygon(upper, closed=True,
                         facecolor=fill_colors[0],
                         edgecolor="none", alpha=alpha,
                         zorder=z*10 + 1)
    ax.add_patch(lower_poly)
    ax.add_patch(upper_poly)
    # Plane outline
    outline = Polygon(pts, closed=True, facecolor="none",
                      edgecolor=edge, linewidth=1.6,
                      zorder=z*10 + 2)
    ax.add_patch(outline)
    return pts


def draw_components(ax, z, x0, y0, comps, edge):
    """Draw component boxes in one centered row inside the plane."""
    n = len(comps)
    # Layout: 1 row, centered horizontally, leaving title space
    # at the top.
    pad_x = 0.4
    pad_y_top = 0.95   # space for plane label
    pad_y_bot = 0.25
    usable_w = PW - 2 * pad_x
    cell_w = usable_w / n
    box_w = cell_w - 0.30
    box_h = PH - pad_y_top - pad_y_bot
    for i, (text, color) in enumerate(comps):
        cx_logical = x0 + pad_x + i * cell_w + (cell_w - box_w) / 2
        cy_logical = y0 + pad_y_bot
        bx, by = iso_xy(cx_logical, cy_logical, z)
        sh = FancyBboxPatch((bx + 0.05, by - 0.07), box_w, box_h,
                            boxstyle="round,pad=0.03,rounding_size=0.10",
                            facecolor="#000000", edgecolor="none",
                            alpha=0.15, zorder=z*10 + 3)
        ax.add_patch(sh)
        box = FancyBboxPatch((bx, by), box_w, box_h,
                             boxstyle="round,pad=0.03,rounding_size=0.10",
                             facecolor=color, edgecolor=edge,
                             linewidth=0.8, alpha=0.97,
                             zorder=z*10 + 4)
        ax.add_patch(box)
        ax.text(bx + box_w/2, by + box_h/2, text,
                ha="center", va="center", fontsize=7.2,
                color="#222222", zorder=z*10 + 5)


def draw_plane_label(ax, z, x0, y0, label, edge):
    """Draw plane title at top-left."""
    lx_logical = x0 + 0.3
    ly_logical = y0 + PH - 0.40
    tx, ty = iso_xy(lx_logical, ly_logical, z)
    ax.text(tx, ty, label, fontsize=9, weight="bold",
            color=edge, ha="left", va="center",
            zorder=z*10 + 6,
            bbox=dict(boxstyle="round,pad=0.25",
                      facecolor="#ffffff", edgecolor=edge,
                      linewidth=0.8, alpha=0.92))


def draw_inter_plane_arrow(ax, z_from, z_to, x_from, y_from,
                           x_to, y_to, label, color, side="right"):
    """Draw a curved arrow between two planes."""
    p_from = iso_xy(x_from, y_from, z_from)
    p_to = iso_xy(x_to, y_to, z_to)
    # Add intermediate offset for curve
    mid_x = (p_from[0] + p_to[0]) / 2
    if side == "right":
        mid_x += 0.6
    else:
        mid_x -= 0.6
    mid_y = (p_from[1] + p_to[1]) / 2
    # Build a quadratic Bezier curve path
    path_data = [
        (MPath.MOVETO, p_from),
        (MPath.CURVE3, (mid_x, mid_y)),
        (MPath.CURVE3, p_to),
    ]
    codes, verts = zip(*path_data)
    path = MPath(verts, codes)
    patch = PathPatch(path, facecolor="none", edgecolor=color,
                      lw=1.6, zorder=200,
                      capstyle="round")
    ax.add_patch(patch)
    # Arrowhead at p_to
    dx = p_to[0] - mid_x
    dy = p_to[1] - mid_y
    norm = np.hypot(dx, dy) + 1e-9
    dx /= norm
    dy /= norm
    head = FancyArrow(p_to[0] - 0.25*dx, p_to[1] - 0.25*dy,
                      0.25*dx, 0.25*dy, width=0.0,
                      head_width=0.22, head_length=0.25,
                      length_includes_head=True,
                      facecolor=color, edgecolor=color,
                      zorder=201)
    ax.add_patch(head)
    # Label
    if label:
        lx_o = 0.25 if side == "right" else -0.25
        ax.text(mid_x + lx_o, mid_y + 0.15, label,
                color=color, fontsize=6.8, ha="left" if side == "right" else "right",
                va="center", style="italic", weight="bold",
                bbox=dict(boxstyle="round,pad=0.20",
                          facecolor="#ffffff", edgecolor=color,
                          linewidth=0.5, alpha=0.92),
                zorder=202)


def main():
    fig = plt.figure(figsize=(11.0, 4.6))
    ax = fig.add_subplot(111)

    X0, Y0 = 1.0, 0.5

    # Draw planes bottom-up so upper planes occlude lower
    plane_corners = {}
    for spec in PLANES:
        z = spec["z"]
        corners = draw_iso_plane(ax, z, X0, Y0,
                                 spec["fill"], spec["edge"])
        plane_corners[z] = corners
        draw_components(ax, z, X0, Y0, spec["comps"], spec["edge"])
        draw_plane_label(ax, z, X0, Y0, spec["label"], spec["edge"])

    # Theorem coverage ribbon on the far right
    for spec in PLANES:
        z = spec["z"]
        tx_logical = X0 + PW + 1.5
        ty_logical = Y0 + PH / 2
        tx, ty = iso_xy(tx_logical, ty_logical, z)
        ax.text(tx, ty, spec["theorems"], fontsize=7.0,
                color=spec["edge"], ha="left", va="center",
                weight="bold",
                bbox=dict(boxstyle="round,pad=0.25",
                          facecolor="#fafaff", edgecolor=spec["edge"],
                          linewidth=0.7, alpha=0.95),
                zorder=z*10 + 7)

    # Inter-plane arrows (between plane top of lower and bottom of
    # next upper plane in screen coords)
    # P1 -> P2: raw metrics
    draw_inter_plane_arrow(ax, 0, 1, X0 + 1.5, Y0 + PH,
                           X0 + 1.5, Y0,
                           "raw metrics", "#bf8f00", side="left")
    # P2 -> P3: cross-observability
    draw_inter_plane_arrow(ax, 1, 2, X0 + 2.5, Y0 + PH,
                           X0 + 2.5, Y0,
                           "cross-observability", "#385723",
                           side="left")
    # P3 -> P2: bounded blacklist B_t (downward)
    draw_inter_plane_arrow(ax, 2, 1, X0 + PW - 2.5, Y0,
                           X0 + PW - 2.5, Y0 + PH,
                           r"$\mathcal{B}_t$ ($|\mathcal{B}_t|<f$)",
                           "#1f4e79", side="right")
    # P2 -> P4: ordered blockchain state (upward, skipping P3)
    draw_inter_plane_arrow(ax, 1, 3, X0 + PW - 0.5, Y0 + PH,
                           X0 + PW - 0.5, Y0,
                           "consented state", "#c55a11",
                           side="right")

    # Bottom strip: 60-experiment coverage breakdown
    coverage_text = (r"$60$-experiment coverage:    "
                     r"Normal ($15$)  $|$  Node failures ($15$)  $|$  "
                     r"Network partitions ($15$)  $|$  "
                     r"Byzantine scenarios ($15$)")
    ax.text(X0 + PW / 2 + 0.7, Y0 - 0.55, coverage_text,
            fontsize=7.5, ha="center", va="center",
            color="#222222", weight="bold",
            bbox=dict(boxstyle="round,pad=0.4",
                      facecolor="#fffbe7",
                      edgecolor="#bf8f00", linewidth=1.0))

    # Compute overall plot bounds from drawn elements
    ax.set_xlim(-0.5, X0 + PW + DX*3 + 8.0)
    ax.set_ylim(-1.5, Y0 + PH + DY*3 + 1.5)
    ax.set_aspect("equal")
    ax.axis("off")

    fig.suptitle("Comprehensive Multi-Plane Security Architecture "
                 "with Theorems & Experimental Coverage",
                 fontsize=10.5, y=0.97, weight="bold")
    plt.tight_layout(rect=[0, 0, 1, 0.95])

    out_pdf = OUT / "fig9_architecture_v17.pdf"
    out_png = OUT / "fig9_architecture_v17.png"
    plt.savefig(out_pdf, dpi=300, bbox_inches="tight",
                pad_inches=0.05)
    plt.savefig(out_png, dpi=180, bbox_inches="tight",
                pad_inches=0.05)
    plt.close(fig)
    print(f"Wrote {out_pdf}")
    print(f"Wrote {out_png}")


if __name__ == "__main__":
    main()
