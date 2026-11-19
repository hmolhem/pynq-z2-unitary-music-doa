"""Coherent sources: resolution probability of the bit-exact Tier 3 chain vs. relative phase.

Forward-backward averaging (built into unitary MUSIC) restores the rank of two coherent
sources unless their relative phase psi is a multiple of pi. This script fixes psi and
measures how often the bit-exact Tier 3 chain resolves both sources.

Scene (same as sweep_tier3_chain.py): 8-element virtual ULA, sources at -10 and 5 deg,
M = 128 snapshots, both sources carry the same circular complex Gaussian sequence with
unit power, the second one multiplied by exp(j psi); white circular complex Gaussian noise
with power 10^(-SNR/10) per element. A trial is resolved when both estimates are within
2 deg of the true angles (same criterion as sweep_tier3_chain.py).

Phase grid: 1-deg steps on 0..20 and 160..180 deg, 10-deg steps in between.
Seeds: numpy default_rng(SEED + 1000 * snr_index + phase_index), so every
(SNR, psi) point is reproducible on its own.

Usage:  python phase_sweep.py [n_trials]          (default 100, about 3 minutes)
Output: results/phase_sweep.csv, results/phase_sweep.pdf, results/phase_sweep.png
"""

import csv
import os
import sys

import numpy as np

from chain_bitexact import tier3_doa
from doa_golden import MimoArray

ARR = MimoArray()
TRUE = np.array([-10.0, 5.0])
M = 128
SNRS = [0, 10, 20]
TOL = 2.0
SEED = 7000
PSI_DEG = np.concatenate([np.arange(0, 21, 1.0), np.arange(30, 151, 10.0), np.arange(160, 181, 1.0)])


def wilson(k: int, n: int, z: float = 1.96):
    """95 % Wilson score interval of a binomial proportion."""
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def resolved_count(psi_deg: float, snr_db: float, n_trials: int, rng: np.random.Generator) -> int:
    a = ARR.steering(TRUE)
    sigma = 10 ** (-snr_db / 20)
    ok = 0
    for _ in range(n_trials):
        s = (rng.standard_normal(M) + 1j * rng.standard_normal(M)) / np.sqrt(2)
        src = np.vstack([s, s * np.exp(1j * np.deg2rad(psi_deg))])
        n = sigma * (rng.standard_normal((ARR.n_virtual, M))
                     + 1j * rng.standard_normal((ARR.n_virtual, M))) / np.sqrt(2)
        est = np.sort(np.asarray(tier3_doa(a @ src + n), float))
        ok += int(est.size == 2 and np.all(np.abs(est - TRUE) < TOL))
    return ok


def main(n_trials: int):
    here = os.path.dirname(os.path.abspath(__file__))
    out_dir = os.path.join(here, "results")
    os.makedirs(out_dir, exist_ok=True)

    rows = []
    for si, snr in enumerate(SNRS):
        for pi_, psi in enumerate(PSI_DEG):
            rng = np.random.default_rng(SEED + 1000 * si + pi_)
            k = resolved_count(psi, snr, n_trials, rng)
            lo, hi = wilson(k, n_trials)
            rows.append(dict(snr_db=snr, psi_deg=psi, trials=n_trials, resolved=k,
                             p_res=k / n_trials, wilson_lo=round(lo, 4), wilson_hi=round(hi, 4)))
        print(f"SNR {snr:3d} dB: " + " ".join(f"{r['psi_deg']:g}:{r['p_res']:.2f}"
                                             for r in rows if r["snr_db"] == snr))

    csv_path = os.path.join(out_dir, "phase_sweep.csv")
    with open(csv_path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print("wrote", csv_path)

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({"font.size": 8, "font.family": "serif"})
    fig, ax = plt.subplots(figsize=(3.4, 1.9))
    for snr, style in zip(SNRS, ["-.", "-", "--"]):
        pts = [r for r in rows if r["snr_db"] == snr]
        ax.plot([r["psi_deg"] for r in pts], [r["p_res"] for r in pts], style, lw=1.2, label=f"{snr} dB")
    ax.set_xlabel("Relative phase of the coherent sources (deg)")
    ax.set_ylabel("Resolution prob.")
    ax.set_xlim(0, 180)
    ax.set_ylim(-0.03, 1.03)
    ax.set_xticks(range(0, 181, 30))
    ax.grid(alpha=0.3)
    ax.legend(loc="center", frameon=False, title="SNR")
    fig.tight_layout(pad=0.2)
    for ext in ("pdf", "png"):
        fig.savefig(os.path.join(out_dir, f"phase_sweep.{ext}"), dpi=200)
    print("wrote", os.path.join(out_dir, "phase_sweep.pdf"))


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 100)
