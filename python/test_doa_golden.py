import numpy as np
import pytest

from doa_golden import (
    MimoArray, Quantizers, complex_music_doa, jacobi_evd, make_fixed,
    real_steering_table, real_valued_scm, scm, simulate_snapshots,
    unitary_matrix, unitary_music_doa,
)

ARR = MimoArray()
GRID = np.arange(-90.0, 90.0 + 1e-9, 1.0)


def test_virtual_array_is_filled_ula():
    p = ARR.virtual_positions
    assert ARR.n_virtual == 8
    assert np.allclose(np.diff(p), 0.5)
    assert np.isclose(p.mean(), 0.0)


def test_unitary_matrix_is_unitary():
    for n in (4, 7, 8):
        q = unitary_matrix(n)
        assert np.allclose(q.conj().T @ q, np.eye(n))


def test_real_steering_is_real():
    real_steering_table(ARR, GRID)  # asserts internally


def test_real_scm_equals_unitary_transform_of_fb_scm():
    rng = np.random.default_rng(0)
    x = simulate_snapshots(ARR, [-20, 15], 10, 128, rng)
    n = ARR.n_virtual
    j = np.fliplr(np.eye(n))
    r = scm(x)
    r_fb = 0.5 * (r + j @ r.conj() @ j)
    q = unitary_matrix(n)
    expected = q.conj().T @ r_fb @ q
    assert np.max(np.abs(expected.imag)) < 1e-12
    assert np.allclose(real_valued_scm(x), expected.real)


def test_jacobi_matches_eigh():
    rng = np.random.default_rng(1)
    m = rng.standard_normal((8, 8))
    a = m @ m.T
    res = jacobi_evd(a, n_sweeps=6)
    w = np.sort(np.linalg.eigvalsh(a))[::-1]
    assert np.allclose(res.eigvals, w, rtol=1e-10, atol=1e-10)
    v = res.eigvecs
    assert np.allclose(v.T @ v, np.eye(8), atol=1e-10)
    assert np.allclose(v @ np.diag(res.eigvals) @ v.T, a, atol=1e-9)


@pytest.mark.parametrize("coherent", [False, True])
def test_two_sources_resolved_high_snr(coherent):
    rng = np.random.default_rng(2)
    true = np.array([-20.0, 15.0])
    x = simulate_snapshots(ARR, true, 20, 128, rng, coherent=coherent)
    est = unitary_music_doa(x, ARR, 2, GRID)
    assert np.max(np.abs(est - true)) < 0.5


def test_complex_music_baseline():
    rng = np.random.default_rng(3)
    true = np.array([-20.0, 15.0])
    x = simulate_snapshots(ARR, true, 20, 128, rng)
    assert np.max(np.abs(complex_music_doa(x, ARR, 2, GRID) - true)) < 0.5


def test_fixed_point_close_to_float():
    rng = np.random.default_rng(4)
    true = np.array([-20.0, 15.0])
    x = simulate_snapshots(ARR, true, 15, 128, rng)
    qz = Quantizers(make_fixed(16, 1), make_fixed(32, 6), make_fixed(24, 6), make_fixed(24, 6))
    est_fx = unitary_music_doa(x, ARR, 2, GRID, qz=qz)
    est_fl = unitary_music_doa(x, ARR, 2, GRID)
    assert np.max(np.abs(est_fx - est_fl)) < 0.2


def test_bitexact_scm_matches_float_within_half_lsb():
    from scm_bitexact import quantize_input, raw_to_float, scm_unitary_raw
    rng = np.random.default_rng(5)
    for coherent in (False, True):
        x = simulate_snapshots(ARR, [-10, 5], 10, 128, rng, coherent=coherent)
        x = x / (1.001 * max(np.abs(x.real).max(), np.abs(x.imag).max()))
        xr, xi = quantize_input(x)
        xq = (xr + 1j * xi) * 2.0 ** -15
        err = np.abs(raw_to_float(scm_unitary_raw(xr, xi)) - real_valued_scm(xq))
        assert err.max() <= 2.0 ** -28 + 1e-15
