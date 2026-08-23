"""gen_fig5.py — E6 2D heatmap (W × k-cumulant operational landscape)."""
from pathlib import Path
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

# E6 heatmap data (memory-enabled AUC over W × k_matched)
W_vals = [4, 8, 16, 32, 64, 128]
k_vals = [1, 2, 3, 4]
auc = np.array([
    [0.517, 0.514, 0.514, 0.514],
    [0.559, 0.573, 0.573, 0.573],
    [0.793, 0.800, 0.800, 0.800],
    [0.960, 0.963, 0.963, 0.963],
    [0.999, 0.999, 0.999, 0.999],
    [1.000, 1.000, 1.000, 1.000],
])

fig, ax = plt.subplots(figsize=(4.2, 3.0))
im = ax.imshow(auc, cmap="viridis", aspect="auto",
               extent=[k_vals[0]-0.5, k_vals[-1]+0.5, len(W_vals)-0.5, -0.5],
               vmin=0.5, vmax=1.0, origin="upper")

# Annotate cells
for i, W in enumerate(W_vals):
    for j, k in enumerate(k_vals):
        color = "white" if auc[i, j] < 0.75 else "black"
        ax.text(k, i, f"{auc[i, j]:.2f}",
                ha="center", va="center", color=color, fontsize=8)

ax.set_xticks(k_vals)
ax.set_xticklabels([str(k) for k in k_vals])
ax.set_yticks(range(len(W_vals)))
ax.set_yticklabels([str(W) for W in W_vals])
ax.set_xlabel(r"Matched cumulant order $k$")
ax.set_ylabel(r"Window length $W$")
ax.set_title(r"E6: Operational landscape (W $\times$ k)")

# Mark operational threshold W*=32
ax.axhline(y=3 - 0.5, color="crimson", linestyle="--", linewidth=1.5,
           label=r"$W^\star = 32$ (operational threshold)")
ax.legend(loc="lower right", fontsize=7)

cbar = plt.colorbar(im, ax=ax, label="Detection AUC")
plt.tight_layout()
plt.savefig(OUT / "fig5_e6_landscape.pdf", bbox_inches="tight")
print(f"Wrote: {OUT}/fig5_e6_landscape.pdf")
