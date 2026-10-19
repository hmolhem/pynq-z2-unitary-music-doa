import math

import numpy as np

from chain_bitexact import tier2_doa
from doa_golden import MimoArray, simulate_snapshots
from gen_jacobi_vectors import make_r_frames
from jacobi_bitexact import (
    ANG_FRAC, CS_FRAC, cordic_rotation, cordic_vectoring, jacobi_float, jacobi_raw,
)
from scm_bitexact import OUT_FRAC

GRID = np.arange(-90.0, 90.0 + 1e-9, 1.0)


def test_cordic_rotation_accuracy():
    for th in np.linspace(-math.pi / 4, math.pi / 4, 41):
        c, s = cordic_rotation(int(round(th * 2 ** ANG_FRAC)))
        assert abs(c * 2.0 ** -CS_FRAC - math.cos(th)) < 3e-7
        assert abs(s * 2.0 ** -CS_FRAC - math.sin(th)) < 3e-7


def test_cordic_vectoring_accuracy():
    rng = np.random.default_rng(3)
    for _ in range(200):
        x = int(rng.integers(0, 2 ** 31))
        y = int(rng.integers(-2 ** 31, 2 ** 31))
        ang = cordic_vectoring(x, y) * 2.0 ** -ANG_FRAC
        assert abs(ang - math.atan2(y, x)) < 3e-7
    # tiny inputs are normalized first, so the angle stays accurate
    assert abs(cordic_vectoring(3, 1) * 2.0 ** -ANG_FRAC - math.atan2(1, 3)) < 3e-7


def test_jacobi_eigenvalues_and_vectors_match_eigh():
    for r in make_r_frames():
        rf = r.astype(float) * 2.0 ** -OUT_FRAC
        lam, vec = jacobi_float(*jacobi_raw(r))
        ref = np.sort(np.linalg.eigvalsh(rf))[::-1]
        assert np.max(np.abs(lam - ref)) < 1e-5
        assert np.max(np.abs(vec.T @ vec - np.eye(8))) < 1e-6
        scale = max(np.linalg.norm(rf), 1e-12)
        assert np.linalg.norm(vec @ np.diag(lam) @ vec.T - rf) / scale < 1e-4


def test_tier2_chain_recovers_doa():
    arr = MimoArray()
    for coherent in (False, True):
        rng = np.random.default_rng(11)
        x = simulate_snapshots(arr, [-10, 5], 15, 128, rng, coherent=coherent)
        est = tier2_doa(x, arr, 2, GRID)
        assert np.max(np.abs(est - np.array([-10.0, 5.0]))) < 1.0
