"""Word-length study: how narrow can each stage be before DOA accuracy drops?

Word lengths scaled together from configuration B (12/20/18/18): input W bits,
covariance W + 8, Jacobi W + 6, MUSIC W + 6 (integer bits as in the hardware). Float model with quantizer
hooks (doa_golden.Quantizers), 4 Jacobi sweeps, two sources at -10/5 deg,
M = 128, 200 trials per point.

Usage:  python dse_wordlength.py [n_trials]
Output: results/dse_wordlength.csv
"""

import csv
import os
import sys

import numpy as np

from doa_golden import MimoArray, Quantizers, make_fixed, simulate_snapshots, unitary_music_doa

ARR = MimoArray()
GRID = np.arange(-90.0, 90.0 + 1e-9, 1.0)
TRUE = np.array([-10.0, 5.0])
SCENES = [(False, 10), (False, 20), (True, 10), (True, 20)]
TOL = 2.0


def qz_uniform(w: int) -> Quantizers:
    return Quantizers(make_fixed(w, 1), make_fixed(w + 8, 5), make_fixed(w + 6, 6), make_fixed(w + 6, 5))


def evaluate(qz, n_trials: int) -> dict:
    out = {}
    for coherent, snr in SCENES:
        rng = np.random.default_rng(2000 + snr + (500 if coherent else 0))
        err, ok = [], 0
        for _ in range(n_trials):
            x = simulate_snapshots(ARR, TRUE, snr, 128, rng, coherent=coherent)
            e = np.sort(unitary_music_doa(x, ARR, 2, GRID, n_sweeps=4, qz=qz)) - TRUE
            err.append(e)
            ok += int(np.all(np.abs(e) < TOL))
        tag = f"{'coh' if coherent else 'unc'}_{snr}dB"
        out[f"rmse_{tag}"] = float(np.sqrt(np.mean(np.square(err))))
        out[f"p_{tag}"] = ok / n_trials
    return out


def main(n_trials: int):
    rows = [dict(config="float", **evaluate(None, n_trials))]
    print(rows[-1])
    for w in (16, 14, 12, 10, 9, 8, 7, 6):
        rows.append(dict(config=f"uniform W={w}", **evaluate(qz_uniform(w), n_trials)))
        r = rows[-1]
        print(r["config"], {k: round(v, 4) for k, v in r.items() if k != "config"})
    os.makedirs("results", exist_ok=True)
    with open("results/dse_wordlength.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 200)
