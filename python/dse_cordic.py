"""Design-space study: CORDIC iterations in the Jacobi kernel vs accuracy.

For 12, 16, 20 and 24 iterations: eigenvalue error of the bit-exact model
against LAPACK on the Jacobi test matrices, and DOA accuracy of the whole
fixed-point estimator against float (Monte Carlo). Latency and resources of
the same variants come from hls/run_dse.ps1.

Usage:  python dse_cordic.py [n_trials]
Output: results/dse_cordic.csv
"""

import csv
import math
import os
import sys

import numpy as np

import jacobi_bitexact as jb
from chain_bitexact import tier3_doa
from doa_golden import MimoArray, simulate_snapshots, unitary_music_doa
from gen_jacobi_vectors import make_r_frames
from scm_bitexact import OUT_FRAC

ARR = MimoArray()
GRID = np.arange(-90.0, 90.0 + 1e-9, 1.0)
TRUE = np.array([-10.0, 5.0])


def set_cordic(n: int) -> None:
    jb.N_CORDIC = n
    jb.ATAN_TABLE = [int(round(math.atan(2.0 ** -i) * 2 ** jb.ANG_FRAC)) for i in range(n)]
    k = 1.0
    for i in range(n):
        k /= math.sqrt(1.0 + 2.0 ** (-2 * i))
    jb.CORDIC_KINV = int(round(k * 2 ** jb.CS_FRAC))


def main(n_trials: int):
    frames = make_r_frames()
    rows = []
    for n in (12, 16, 20, 24):
        set_cordic(n)
        eig_err = 0.0
        for r in frames:
            rf = r.astype(float) * 2.0 ** -OUT_FRAC
            lam, _ = jb.jacobi_float(*jb.jacobi_raw(r))
            ref = np.sort(np.linalg.eigvalsh(rf))[::-1]
            eig_err = max(eig_err, float(np.max(np.abs(lam - ref)) / max(ref[0], 1e-12)))
        row = dict(n_cordic=n, max_rel_eig_error=eig_err)
        for coherent in (False, True):
            for snr in (0, 10, 20):
                rng = np.random.default_rng(1000 + snr + (500 if coherent else 0))
                ef, eh = [], []
                for _ in range(n_trials):
                    x = simulate_snapshots(ARR, TRUE, snr, 128, rng, coherent=coherent)
                    ef.append(np.sort(unitary_music_doa(x, ARR, 2, GRID, n_sweeps=4)) - TRUE)
                    eh.append(np.sort(tier3_doa(x)) - TRUE)
                tag = f"{'coh' if coherent else 'unc'}_{snr}dB"
                row[f"rmse_float_{tag}"] = float(np.sqrt(np.mean(np.square(ef))))
                row[f"rmse_fixed_{tag}"] = float(np.sqrt(np.mean(np.square(eh))))
        rows.append(row)
        print(n, f"max rel eig error {eig_err:.2e}",
              " ".join(f"{k[11:]}={v:.4f}" for k, v in row.items() if k.startswith("rmse_fixed")))
    set_cordic(24)
    os.makedirs("results", exist_ok=True)
    with open("results/dse_cordic.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 100)
