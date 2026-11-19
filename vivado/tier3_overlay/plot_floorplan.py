"""Floorplan of the routed Tier 3 overlay from the CSV files of export_floorplan_power.tcl.

Usage:  python plot_floorplan.py [output_dir]
Writes: <output_dir>/floorplan_tier3.pdf and .png
"""
import csv
import sys
from collections import Counter
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

COLORS = {
    "scm_unitary": "#1f77b4",
    "jacobi_evd": "#d62728",
    "music_doa": "#2ca02c",
    "axi_dma": "#9467bd",
    "infrastructure": "#8c8c8c",
}
LABELS = {
    "scm_unitary": "scm_unitary (covariance)",
    "jacobi_evd": "jacobi_evd (EVD)",
    "music_doa": "music_doa (MUSIC + peaks)",
    "axi_dma": "AXI DMA",
    "infrastructure": "interconnect, timer, reset",
}


def read(path):
    with open(path, newline="") as fh:
        return list(csv.DictReader(fh))


def kind(site_type):
    if site_type.startswith("SLICE"):
        return "slice"
    if site_type.startswith("DSP"):
        return "dsp"
    if site_type.startswith("RAMB"):
        return "bram"
    return None


def main(out_dir):
    out = Path(out_dir)
    all_sites = read(out / "placement_all.csv")
    used = read(out / "placement_used.csv")

    plt.rcParams.update({"font.size": 8, "font.family": "serif"})
    fig, ax = plt.subplots(figsize=(3.5, 4.6))
    marker = {"slice": ("s", 2.0), "dsp": ("D", 5.0), "bram": ("s", 7.0)}

    # background: every site of the device
    for k, (m, size) in marker.items():
        pts = [(int(s["rpm_x"]), int(s["rpm_y"])) for s in all_sites if kind(s["site_type"]) == k]
        if pts:
            xs, ys = zip(*pts)
            ax.scatter(xs, ys, s=size, marker=m, c="#ececec", linewidths=0, zorder=1)

    # used sites, coloured by block
    for block, color in COLORS.items():
        for k, (m, size) in marker.items():
            pts = [(int(s["rpm_x"]), int(s["rpm_y"])) for s in used
                   if s["block"] == block and kind(s["site_type"]) == k]
            if pts:
                xs, ys = zip(*pts)
                ax.scatter(xs, ys, s=size * (1.6 if k != "slice" else 1.0), marker=m, c=color,
                           linewidths=0, zorder=2 if k == "slice" else 3)
        ax.scatter([], [], s=12, marker="s", c=color, label=LABELS[block])

    ax.set_aspect("equal")
    ax.set_xticks([])
    ax.set_yticks([])
    for spine in ax.spines.values():
        spine.set_linewidth(0.5)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.01), ncol=2, frameon=False,
              handletextpad=0.3, columnspacing=0.8, fontsize=7)
    fig.tight_layout(pad=0.2)
    fig.savefig(out / "floorplan_tier3.pdf")
    fig.savefig(out / "floorplan_tier3.png", dpi=300)

    # short summary for the text
    per_block = Counter((s["block"], kind(s["site_type"])) for s in used)
    for block in COLORS:
        print(f"{block:16s} slices {per_block[(block, 'slice')]:5d}  "
              f"DSP {per_block[(block, 'dsp')]:4d}  BRAM {per_block[(block, 'bram')]:3d}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "output")
