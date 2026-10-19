"""
chain_bitexact.py -- The Tier 2 hardware chain, bit-exact up to the EVD.

    ARM : frame scaling, 16-bit quantization           (normalize_frame)
    PL  : unitary SCM          scm_bitexact.scm_unitary_raw
    PL  : Jacobi EVD           jacobi_bitexact.jacobi_raw
    ARM : sort, signal subspace, MUSIC denominator, peak search (float)

Whatever this returns is what the Tier 2 overlay returns on the board.
"""

from __future__ import annotations

import numpy as np

from doa_golden import (
    MimoArray, find_peaks, music_spectrum_signal_subspace, normalize_frame,
    real_steering_table,
)
from jacobi_bitexact import jacobi_float, jacobi_raw
from scm_bitexact import quantize_input, scm_unitary_raw


def tier2_doa(x: np.ndarray, array: MimoArray, k: int, grid_deg: np.ndarray,
              b_table: np.ndarray | None = None, refine: bool = True):
    xs, _ = normalize_frame(x)
    xr, xi = quantize_input(xs)
    lam, vec = jacobi_float(*jacobi_raw(scm_unitary_raw(xr, xi)))
    b = real_steering_table(array, grid_deg) if b_table is None else b_table
    denom = music_spectrum_signal_subspace(vec[:, :k], b)
    return find_peaks(denom, grid_deg, k, refine)
