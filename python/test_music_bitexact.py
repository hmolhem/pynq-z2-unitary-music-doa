import numpy as np

from chain_bitexact import tier3_doa
from doa_golden import (
    MimoArray, find_peaks, music_spectrum_signal_subspace, real_steering_table,
    simulate_snapshots,
)
from gen_music_vectors import make_frames
from jacobi_bitexact import jacobi_float
from music_bitexact import B_FRAC, B_ROM, GRID_DEG, angles_deg, music_raw

ARR = MimoArray()


def test_steering_rom_matches_table():
    b = real_steering_table(ARR, GRID_DEG)
    assert np.max(np.abs(B_ROM * 2.0 ** -B_FRAC - b)) <= 2.0 ** -(B_FRAC + 1)
    assert np.allclose(np.sum(b ** 2, axis=0), 8.0)      # ||b||^2 = N, used as a constant


def test_music_matches_float_on_hardware_eigenvectors():
    b = real_steering_table(ARR, GRID_DEG)
    frames, _ = make_frames()
    for d_eig, v in frames[:-4]:                     # skip the crafted fallback inputs
        lam, vec = jacobi_float(d_eig, v)
        if lam[1] - lam[2] <= 0:                     # no distinct signal subspace (silence)
            continue
        flt = find_peaks(music_spectrum_signal_subspace(vec[:, :2], b), GRID_DEG, 2)
        fix = angles_deg(music_raw(d_eig, v)[0])
        assert np.max(np.abs(np.sort(flt) - fix)) < 0.05


def test_tier3_chain_recovers_doa():
    for coherent in (False, True):
        rng = np.random.default_rng(11)
        x = simulate_snapshots(ARR, [-10, 5], 15, 128, rng, coherent=coherent)
        assert np.max(np.abs(tier3_doa(x) - np.array([-10.0, 5.0]))) < 1.0
