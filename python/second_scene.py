"""Second test scene: a closer, off-broadside source pair through the bit-exact Tier 3 chain.

All other results use sources at -10 and 5 deg (15 deg apart, about one beamwidth of the
8-element virtual ULA). This script repeats the Monte Carlo study for sources at 20 and 28 deg:
8 deg apart, which is below the beamwidth, and away from broadside, where the spatial
frequency sin(theta) changes more slowly. Everything else is unchanged: M = 128 snapshots
(fixed in the hardware), equal-power circular complex Gaussian sources, uniformly random
relative phase in the coherent case, and the 2-deg resolution criterion.

Methods: complex MUSIC (float), unitary MUSIC (float, four Jacobi sweeps), and the bit-exact
Tier 3 chain (identical to the FPGA output). The stochastic two-source CRB (Stoica and
Nehorai 1990) is given for the uncorrelated case. A fourth column, complex MUSIC on a 0.01-deg
grid without refinement, separates the bias of parabolic refinement on the 1-deg grid from the
behaviour of MUSIC itself; the hardware does not use it.

Seeds: numpy default_rng(9000 + 10 * snr_index + (5 if coherent else 0)).

Usage:  python second_scene.py [n_trials]          (default 200, about a minute)
Output: results/second_scene.csv
"""

import csv
import os
import sys

import numpy as np

from chain_bitexact import tier3_doa
from doa_golden import MimoArray, complex_music_doa, simulate_snapshots, unitary_music_doa

ARR = MimoArray()
GRID = np.arange(-90.0, 90.0 + 1e-9, 1.0)
FINE = np.arange(-90.0, 90.0 + 1e-9, 0.01)   # diagnostic only: no grid, no refinement bias
TRUE = np.array([20.0, 28.0])
M = 128
SNRS = [-5, 0, 5, 10, 15, 20]
TOL = 2.0
SEED = 9000


def wilson(k: int, n: int, z: float = 1.96):
    """95 % Wilson score interval of a binomial proportion."""
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def crb_two_sources(snr_db: float, theta=TRUE, m: int = M) -> float:
    """Stochastic CRB, uncorrelated equal-power sources; RMS over both angles, deg."""
    th = np.asarray(theta, float)
    a = ARR.steering(th)
    h = 1e-6
    d = (ARR.steering(th + h) - ARR.steering(th - h)) / (2 * np.deg2rad(h))
    s2 = 10 ** (-snr_db / 10)
    p = np.eye(th.size)
    r = a @ p @ a.conj().T + s2 * np.eye(a.shape[0])
    pa = np.eye(a.shape[0]) - a @ np.linalg.pinv(a)
    hmat = (d.conj().T @ pa @ d) * (p @ a.conj().T @ np.linalg.solve(r, a) @ p).T
    c = s2 / (2 * m) * np.linalg.inv(np.real(hmat))
    return float(np.rad2deg(np.sqrt(np.mean(np.diag(c)))))


def errors(est) -> np.ndarray:
    est = np.sort(np.asarray(est, float))
    if est.size != 2:                      # missing peak: count as far off
        est = np.resize(est, 2) if est.size else np.array([90.0, 90.0])
    return est - TRUE


def main(n_trials: int):
    rows = []
    for coherent in (False, True):
        for i, snr in enumerate(SNRS):
            rng = np.random.default_rng(SEED + 10 * i + (5 if coherent else 0))
            err = {"complex": [], "unitary": [], "tier3": [], "complex_fine": []}
            for _ in range(n_trials):
                x = simulate_snapshots(ARR, TRUE, snr, M, rng, coherent=coherent)
                err["complex"].append(errors(complex_music_doa(x, ARR, 2, GRID)))
                err["unitary"].append(errors(unitary_music_doa(x, ARR, 2, GRID, n_sweeps=4)))
                err["tier3"].append(errors(tier3_doa(x)))
                err["complex_fine"].append(errors(complex_music_doa(x, ARR, 2, FINE, refine=False)))
            row = dict(coherent=coherent, snr_db=snr, trials=n_trials,
                       crb_deg=crb_two_sources(snr))
            for k, e in err.items():
                e = np.array(e)
                ok = int(np.sum(np.all(np.abs(e) < TOL, axis=1)))
                row[f"rmse_{k}"] = float(np.sqrt(np.mean(e ** 2)))
                row[f"res_{k}"] = ok / n_trials
                if k == "tier3":
                    row["res_tier3_lo"], row["res_tier3_hi"] = wilson(ok, n_trials)
                    row["bias1_tier3"], row["bias2_tier3"] = (float(v) for v in e.mean(axis=0))
            rows.append(row)
            print(f"{'coh' if coherent else 'unc'} {snr:4d} dB  CRB {row['crb_deg']:.3f}  "
                  f"RMSE c/u/t3 {row['rmse_complex']:.3f}/{row['rmse_unitary']:.3f}/"
                  f"{row['rmse_tier3']:.3f}  fine {row['rmse_complex_fine']:.3f}  res c/u/t3 {row['res_complex']:.3f}/"
                  f"{row['res_unitary']:.3f}/{row['res_tier3']:.3f} "
                  f"[{row['res_tier3_lo']:.2f}, {row['res_tier3_hi']:.2f}]")
    os.makedirs("results", exist_ok=True)
    with open("results/second_scene.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 200)
