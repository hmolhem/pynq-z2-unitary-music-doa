"""
doa_golden.py -- Golden reference model for the PYNQ-Z2 fixed-point
real-valued (unitary) PCA/MUSIC DOA accelerator.

Processing chain (each stage maps to one hardware block):

    X (N x M complex, virtual MIMO array)
      -> [1] SCM:      R = X X^H / M
      -> [2] Unitary:  R_re = Re{ Q^H R Q }          (real symmetric N x N)
      -> [3] PCA/EVD:  cyclic Jacobi, fixed number of sweeps
      -> [4] MUSIC:    P(theta) = 1 / (N - sum_k (e_k^T b(theta))^2)
      -> [5] Peaks:    K largest local maxima + parabolic refinement

Every arithmetic stage accepts a quantizer hook `q` so the same code serves
as the floating-point reference (q = identity) and as the word-length
emulation model for the fixed-point HLS design.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

import numpy as np

Quantizer = Callable[[np.ndarray], np.ndarray]


def _identity(x: np.ndarray) -> np.ndarray:
    return x


# ---------------------------------------------------------------------------
# Array geometry: colocated MIMO -> virtual ULA
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class MimoArray:
    """Colocated MIMO array whose virtual aperture is a filled ULA.

    Rx spacing d_r = d (wavelengths); Tx spacing d_t = n_rx * d, so the
    virtual array (Tx x Rx sum co-array) is a ULA of n_tx*n_rx elements.
    Positions are centred on the array midpoint so the steering vector is
    conjugate-centro-symmetric (required for the real-valued transform).
    """

    n_tx: int = 2
    n_rx: int = 4
    d: float = 0.5  # element spacing in wavelengths

    @property
    def n_virtual(self) -> int:
        return self.n_tx * self.n_rx

    @property
    def tx_positions(self) -> np.ndarray:
        return np.arange(self.n_tx) * self.n_rx * self.d

    @property
    def rx_positions(self) -> np.ndarray:
        return np.arange(self.n_rx) * self.d

    @property
    def virtual_positions(self) -> np.ndarray:
        p = (self.tx_positions[:, None] + self.rx_positions[None, :]).ravel()
        p = np.sort(p)
        return p - p.mean()

    def steering(self, theta_deg) -> np.ndarray:
        """Virtual steering matrix, shape (N, len(theta))."""
        th = np.deg2rad(np.atleast_1d(np.asarray(theta_deg, dtype=float)))
        return np.exp(1j * 2 * np.pi * np.outer(self.virtual_positions, np.sin(th)))


# ---------------------------------------------------------------------------
# Signal generation
# ---------------------------------------------------------------------------
def simulate_snapshots(
    array: MimoArray,
    theta_deg,
    snr_db: float,
    n_snap: int,
    rng: np.random.Generator,
    coherent: bool = False,
    source_model: str = "gaussian",
) -> np.ndarray:
    """Virtual-array snapshots after matched filtering, shape (N, M).

    source_model:
        "gaussian" -- circular complex Gaussian amplitudes (Swerling-II like)
        "doppler"  -- unit-modulus targets with distinct Doppler phase ramps
    coherent: all sources share the same amplitude sequence (worst case
              for plain MUSIC; handled by forward-backward/unitary MUSIC).
    """
    theta = np.atleast_1d(theta_deg)
    k = theta.size
    a = array.steering(theta)
    if source_model == "gaussian":
        s = (rng.standard_normal((k, n_snap)) + 1j * rng.standard_normal((k, n_snap))) / np.sqrt(2)
    elif source_model == "doppler":
        fd = rng.uniform(-0.5, 0.5, size=(k, 1))
        ph0 = rng.uniform(0, 2 * np.pi, size=(k, 1))
        s = np.exp(1j * (2 * np.pi * fd * np.arange(n_snap)[None, :] + ph0))
    else:
        raise ValueError(source_model)
    if coherent:
        s = np.repeat(s[:1], k, axis=0) * np.exp(1j * rng.uniform(0, 2 * np.pi, size=(k, 1)))
    sigma = 10 ** (-snr_db / 20)
    n = sigma * (rng.standard_normal((array.n_virtual, n_snap))
                 + 1j * rng.standard_normal((array.n_virtual, n_snap))) / np.sqrt(2)
    return a @ s + n


def normalize_frame(x: np.ndarray, headroom: float = 0.999) -> tuple[np.ndarray, float]:
    """Scale a frame so every real/imag component lies in (-1, 1).

    Done on the ARM before DMA; the scale cancels in MUSIC so it never has
    to be undone. Returns (scaled frame, scale factor).
    """
    peak = max(np.max(np.abs(x.real)), np.max(np.abs(x.imag)), 1e-12)
    g = headroom / peak
    return x * g, g


# ---------------------------------------------------------------------------
# Stage 1-2: SCM and unitary (real-valued) transform
# ---------------------------------------------------------------------------
def unitary_matrix(n: int) -> np.ndarray:
    """Sparse unitary matrix Q_n (Huarng & Yeh 1991) that maps
    conjugate-centro-symmetric vectors to real vectors."""
    m = n // 2
    i_m = np.eye(m)
    pi_m = np.fliplr(i_m)
    if n % 2 == 0:
        q = np.block([[i_m, 1j * i_m], [pi_m, -1j * pi_m]])
    else:
        z = np.zeros((m, 1))
        q = np.block([
            [i_m, z, 1j * i_m],
            [z.T, np.array([[np.sqrt(2)]]), z.T],
            [pi_m, z, -1j * pi_m],
        ])
    return q / np.sqrt(2)


def scm(x: np.ndarray, q: Quantizer = _identity) -> np.ndarray:
    """Complex sample covariance R = X X^H / M."""
    return q(x @ x.conj().T / x.shape[1])


def real_valued_scm(x: np.ndarray, q: Quantizer = _identity) -> np.ndarray:
    """R_re = Re{Q^H R Q}, computed the hardware-friendly way.

    Y = Q^H X costs only additions (Q is +-1, +-j up to 1/sqrt 2). Then
    R_re = (Re Y Re Y^T + Im Y Im Y^T) / M, i.e. one real SCM of a
    2M-column real matrix -- half the multipliers of the complex SCM.
    """
    n, m = x.shape
    y = unitary_matrix(n).conj().T @ x
    yr = q(np.hstack([y.real, y.imag]))
    r = q(yr @ yr.T / m)
    return 0.5 * (r + r.T)


# ---------------------------------------------------------------------------
# Stage 3: cyclic Jacobi EVD (PCA)
# ---------------------------------------------------------------------------
@dataclass
class JacobiResult:
    eigvals: np.ndarray            # descending
    eigvecs: np.ndarray            # columns, same order
    off_norm_per_sweep: list = field(default_factory=list)


def jacobi_evd(
    a: np.ndarray,
    n_sweeps: int = 6,
    q: Quantizer = _identity,
) -> JacobiResult:
    """Cyclic-by-row Jacobi for a real symmetric matrix.

    Fixed sweep count => deterministic hardware latency. Rotation uses the
    numerically stable tangent formula (Golub & Van Loan, Alg. 8.4.1).
    """
    a = q(np.array(a, dtype=float, copy=True))
    n = a.shape[0]
    v = np.eye(n)
    hist = []
    for _ in range(n_sweeps):
        for p in range(n - 1):
            for r in range(p + 1, n):
                apr = a[p, r]
                if apr == 0.0:
                    continue
                tau = (a[r, r] - a[p, p]) / (2.0 * apr)
                t = np.sign(tau) / (abs(tau) + np.sqrt(1.0 + tau * tau)) if tau != 0 else 1.0
                c = float(q(np.array(1.0 / np.sqrt(1.0 + t * t))))
                s = float(q(np.array(t * c)))
                # A <- J^T A J  (rows/cols p and r only)
                ap, ar = a[:, p].copy(), a[:, r].copy()
                a[:, p] = c * ap - s * ar
                a[:, r] = s * ap + c * ar
                ap, ar = a[p, :].copy(), a[r, :].copy()
                a[p, :] = c * ap - s * ar
                a[r, :] = s * ap + c * ar
                a = q(a)
                vp, vr = v[:, p].copy(), v[:, r].copy()
                v[:, p] = c * vp - s * vr
                v[:, r] = s * vp + c * vr
                v = q(v)
        hist.append(float(np.sqrt(np.sum(np.triu(a, 1) ** 2))))
    d = np.diag(a).copy()
    order = np.argsort(d)[::-1]
    return JacobiResult(d[order], v[:, order], hist)


# ---------------------------------------------------------------------------
# Stage 4-5: real-valued MUSIC spectrum and peak search
# ---------------------------------------------------------------------------
def real_steering_table(array: MimoArray, grid_deg: np.ndarray) -> np.ndarray:
    """B = Q^H A(grid), real by construction (stored in ROM on the FPGA)."""
    b = unitary_matrix(array.n_virtual).conj().T @ array.steering(grid_deg)
    assert np.max(np.abs(b.imag)) < 1e-9, "array not centro-symmetric"
    return b.real


def music_spectrum_signal_subspace(
    e_s: np.ndarray, b_table: np.ndarray, q: Quantizer = _identity
) -> np.ndarray:
    """Return the MUSIC *denominator* d(theta) = ||b||^2 - ||E_s^T b||^2.

    Hardware outputs d(theta) (no division needed); peaks of P = 1/d are
    minima of d. Uses only the K signal eigenvectors.
    """
    proj = q(e_s.T @ b_table)                       # K x G
    nb = np.sum(b_table ** 2, axis=0)               # = N for a unit-modulus array
    return q(nb - np.sum(proj ** 2, axis=0))


def find_peaks(
    denom: np.ndarray, grid_deg: np.ndarray, k: int, refine: bool = True
) -> np.ndarray:
    """K deepest local minima of the denominator, optional parabolic refinement."""
    d = denom
    g = len(d)
    is_min = np.zeros(g, dtype=bool)
    is_min[1:-1] = (d[1:-1] < d[:-2]) & (d[1:-1] <= d[2:])
    idx = np.flatnonzero(is_min)
    if idx.size < k:  # fall back: pad with global minima
        extra = [i for i in np.argsort(d) if i not in idx]
        idx = np.concatenate([idx, extra[: k - idx.size]]).astype(int)
    idx = idx[np.argsort(d[idx])[:k]]
    step = grid_deg[1] - grid_deg[0]
    est = []
    for i in idx:
        delta = 0.0
        if refine and 0 < i < g - 1:
            y0, y1, y2 = d[i - 1], d[i], d[i + 1]
            den = y0 - 2 * y1 + y2
            if den > 0:
                delta = 0.5 * (y0 - y2) / den
        est.append(grid_deg[i] + delta * step)
    return np.sort(np.array(est))


# ---------------------------------------------------------------------------
# End-to-end estimators
# ---------------------------------------------------------------------------
@dataclass
class Quantizers:
    """One hook per hardware stage (identity = floating point)."""

    input: Quantizer = _identity
    scm: Quantizer = _identity
    jacobi: Quantizer = _identity
    music: Quantizer = _identity


def unitary_music_doa(
    x: np.ndarray,
    array: MimoArray,
    k: int,
    grid_deg: np.ndarray,
    n_sweeps: int = 6,
    qz: Optional[Quantizers] = None,
    refine: bool = True,
    return_all: bool = False,
):
    """Hardware-equivalent chain: SCM -> unitary -> Jacobi -> MUSIC -> peaks."""
    qz = qz or Quantizers()
    xs, _ = normalize_frame(x)
    xs = qz.input(xs.real) + 1j * qz.input(xs.imag)
    r_re = real_valued_scm(xs, qz.scm)
    evd = jacobi_evd(r_re, n_sweeps, qz.jacobi)
    b = real_steering_table(array, grid_deg)
    denom = music_spectrum_signal_subspace(evd.eigvecs[:, :k], b, qz.music)
    est = find_peaks(denom, grid_deg, k, refine)
    if return_all:
        return est, dict(r_re=r_re, evd=evd, denom=denom)
    return est


def complex_music_doa(x, array, k, grid_deg, refine: bool = True):
    """Conventional complex MUSIC with numpy eigh (software baseline)."""
    r = scm(x)
    w, v = np.linalg.eigh(r)
    e_n = v[:, : array.n_virtual - k]
    a = array.steering(grid_deg)
    denom = np.sum(np.abs(e_n.conj().T @ a) ** 2, axis=0)
    return find_peaks(denom, grid_deg, k, refine)


# ---------------------------------------------------------------------------
# Fixed-point helper (ap_fixed<W,I> emulation: round-to-nearest, saturate)
# ---------------------------------------------------------------------------
def make_fixed(word: int, integer: int, saturate: bool = True) -> Quantizer:
    """Emulate ap_fixed<word, integer, AP_RND, AP_SAT> (integer bits incl. sign)."""
    frac = word - integer
    scale = 2.0 ** frac
    lo = -(2.0 ** (integer - 1))
    hi = 2.0 ** (integer - 1) - 1.0 / scale

    def q(x: np.ndarray) -> np.ndarray:
        y = np.round(np.asarray(x) * scale) / scale
        return np.clip(y, lo, hi) if saturate else y

    q.__name__ = f"ap_fixed<{word},{integer}>"
    return q


def rmse_deg(est: np.ndarray, true: np.ndarray) -> float:
    return float(np.sqrt(np.mean((np.sort(est) - np.sort(true)) ** 2)))
