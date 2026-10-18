"""Generate bit-exact test vectors for hls/scm and cross-check the model.

Usage: python gen_scm_vectors.py  ->  hls/scm/tb/scm_vectors.h
"""

import os

import numpy as np

from doa_golden import MimoArray, normalize_frame, real_valued_scm, simulate_snapshots
from scm_bitexact import (
    M, N, quantize_input, raw_to_float, scm_unitary_raw, write_vectors_header,
)

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "hls", "scm", "tb")


def make_frames():
    arr = MimoArray()
    rng = np.random.default_rng(2026)
    frames = []
    # Realistic frames, scaled on the "ARM" exactly as in deployment
    for theta, snr, coh, model in [
        ([-10, 5], 10, False, "gaussian"),
        ([-10, 5], 20, True, "gaussian"),
        ([30], 30, False, "doppler"),
        ([-40, 0], 0, False, "doppler"),
        ([-60, 45], -5, False, "gaussian"),
    ]:
        x = simulate_snapshots(arr, theta, snr, M, rng, coherent=coh, source_model=model)
        frames.append(normalize_frame(x)[0])
    # Corner cases: extreme input codes and silence
    frames.append(np.full((N, M), (1 - 2 ** -15) * (1 + 1j)))     # +full scale
    frames.append(np.full((N, M), -1.0 - 1.0j))                   # -full scale
    alt = np.where(np.arange(N)[:, None] % 2 == 0, 1.0, -1.0) * np.ones((N, M))
    frames.append(alt * (1 - 2 ** -15) + 1j * (-alt))             # alternating signs
    frames.append(np.zeros((N, M), dtype=complex))                # silence
    frames.append(rng.uniform(-1, 1, (N, M)) + 1j * rng.uniform(-1, 1, (N, M)))
    return frames


def main():
    frames = make_frames()
    os.makedirs(OUT_DIR, exist_ok=True)
    write_vectors_header(os.path.join(OUT_DIR, "scm_vectors.h"), frames)

    # Cross-check: bit-exact model vs float golden model on the same inputs
    worst = 0.0
    peak = 0.0
    for x in frames:
        xr, xi = quantize_input(x)
        xq = (xr + 1j * xi) * 2.0 ** -15
        r_fix = raw_to_float(scm_unitary_raw(xr, xi))
        r_flt = real_valued_scm(xq)
        worst = max(worst, float(np.max(np.abs(r_fix - r_flt))))
        peak = max(peak, float(np.max(np.abs(r_fix))))
    print(f"{len(frames)} frames written to {os.path.normpath(OUT_DIR)}")
    print(f"max |bit-exact - float| = {worst:.3e}  (output LSB = {2**-27:.3e})")
    print(f"max |R| over all frames = {peak:.4f}  (format range +-16)")


if __name__ == "__main__":
    main()
