"""Generate bit-exact test vectors for hls/jacobi and check the model accuracy.

Usage: python gen_jacobi_vectors.py  ->  hls/jacobi/tb/jacobi_vectors.h

Inputs are the R matrices the SCM kernel produces for its own test frames
(so Tier 1 -> Tier 2 is tested end to end), plus corner cases for the
rotation: already diagonal, equal diagonal (theta = +-pi/4), and negative
off-diagonal entries.
"""

import os

import numpy as np

from gen_scm_vectors import make_frames
from jacobi_bitexact import A_FRAC, N, jacobi_float, jacobi_raw, write_vectors_header
from scm_bitexact import OUT_FRAC, quantize_input, scm_unitary_raw

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "hls", "jacobi", "tb")


def to_raw(r: np.ndarray) -> np.ndarray:
    return np.floor(r * 2 ** OUT_FRAC + 0.5).astype(np.int64)


def make_r_frames():
    frames = []
    for x in make_frames():
        xr, xi = quantize_input(x)
        frames.append(scm_unitary_raw(xr, xi))
    rng = np.random.default_rng(7)
    frames.append(to_raw(np.diag(np.linspace(3.5, 0.01, N))))            # diagonal
    frames.append(to_raw(np.full((N, N), 0.5) + np.eye(N)))              # equal diagonal
    b = rng.standard_normal((N, 3))
    frames.append(to_raw(-0.4 * (b @ b.T) / np.max(np.abs(b @ b.T)) + 2 * np.eye(N)))
    g = rng.standard_normal((N, N))
    s = g @ g.T
    frames.append(to_raw(3.9 * s / np.max(np.abs(s))))                   # near full scale
    return frames


def main():
    frames = make_r_frames()
    os.makedirs(OUT_DIR, exist_ok=True)
    write_vectors_header(os.path.join(OUT_DIR, "jacobi_vectors.h"), frames)
    worst_l = worst_rel = 0.0
    for r in frames:
        rf = r.astype(float) * 2.0 ** -OUT_FRAC
        lam, _ = jacobi_float(*jacobi_raw(r))
        ref = np.sort(np.linalg.eigvalsh(rf))[::-1]
        worst_l = max(worst_l, float(np.max(np.abs(lam - ref))))
        worst_rel = max(worst_rel, float(np.max(np.abs(lam - ref)) / max(ref[0], 1e-12)))
    print(f"{len(frames)} frames written to {os.path.normpath(OUT_DIR)}")
    print(f"max |eig - eigh| = {worst_l:.3e}  (A LSB = {2.0 ** -A_FRAC:.3e}),"
          f" relative to lambda_max: {worst_rel:.3e}")


if __name__ == "__main__":
    main()
