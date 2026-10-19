"""Monte Carlo: bit-exact Tier 2 chain (fixed-point SCM + Jacobi) vs float.

Usage:  python sweep_tier2_chain.py [n_trials]
Output: results/tier2_chain_vs_float.csv
"""

import csv
import os
import sys

import numpy as np

from chain_bitexact import tier2_doa
from doa_golden import MimoArray, real_steering_table, simulate_snapshots, unitary_music_doa

ARR = MimoArray()
GRID = np.arange(-90.0, 90.0 + 1e-9, 1.0)
TRUE = np.array([-10.0, 5.0])
M = 128
SNRS = [-10, -5, 0, 5, 10, 15, 20]
TOL = 2.0


def main(n_trials: int):
    b = real_steering_table(ARR, GRID)
    rows = []
    for coherent in (False, True):
        for snr in SNRS:
            rng = np.random.default_rng(1000 + snr + (500 if coherent else 0))
            e_flt, e_fix, ok_flt, ok_fix, same = [], [], 0, 0, 0
            for _ in range(n_trials):
                x = simulate_snapshots(ARR, TRUE, snr, M, rng, coherent=coherent)
                f = np.sort(unitary_music_doa(x, ARR, 2, GRID, n_sweeps=4)) - TRUE
                h = np.sort(tier2_doa(x, ARR, 2, GRID, b)) - TRUE
                e_flt.append(f)
                e_fix.append(h)
                ok_flt += int(np.all(np.abs(f) < TOL))
                ok_fix += int(np.all(np.abs(h) < TOL))
                same += int(np.max(np.abs(f - h)) < 1e-3)
            rows.append(dict(
                coherent=coherent, snr_db=snr, trials=n_trials,
                rmse_float=float(np.sqrt(np.mean(np.square(e_flt)))),
                rmse_tier2=float(np.sqrt(np.mean(np.square(e_fix)))),
                success_float=ok_flt / n_trials, success_tier2=ok_fix / n_trials,
                same_within_1mdeg=same / n_trials))
            r = rows[-1]
            print(f"{'coh' if coherent else 'unc'} {snr:4d} dB  RMSE float {r['rmse_float']:.4f}"
                  f"  tier2 {r['rmse_tier2']:.4f}  succ {r['success_float']:.3f}/"
                  f"{r['success_tier2']:.3f}  same {r['same_within_1mdeg']:.3f}")
    os.makedirs("results", exist_ok=True)
    with open("results/tier2_chain_vs_float.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 200)
