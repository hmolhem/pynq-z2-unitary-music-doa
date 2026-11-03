"""Generate the steering ROM and bit-exact test vectors for hls/music.

Usage: python gen_music_vectors.py
  -> hls/music/music_rom.h        (steering table, shared by C and Python)
  -> hls/music/tb/music_vectors.h (testbench vectors)

Inputs are jacobi_evd outputs (bit-exact), so Tier 2 -> Tier 3 is covered:
the 14 Jacobi test matrices plus realistic frames, including sources near
endfire, a single source, closely spaced sources and pure noise, and two crafted
inputs that exercise the peak-search fallback (zero and one local minimum).
"""

import os

import numpy as np

from doa_golden import MimoArray, normalize_frame, simulate_snapshots, unitary_music_doa
from gen_jacobi_vectors import make_r_frames
from jacobi_bitexact import jacobi_raw
from music_bitexact import angles_deg, music_raw, write_rom_header, write_vectors_header
from scm_bitexact import M, N, quantize_input, scm_unitary_raw

HLS_DIR = os.path.join(os.path.dirname(__file__), "..", "hls", "music")
GRID = np.arange(-90.0, 90.0 + 1e-9, 1.0)


def make_frames():
    arr = MimoArray()
    rng = np.random.default_rng(31)
    frames = [jacobi_raw(r) for r in make_r_frames()]
    scenes = [
        ([-10, 5], 10, False), ([-10, 5], 10, True), ([-80, 85], 15, False),
        ([20], 20, False), ([0, 6], 25, False), ([-45, 30], -5, True), ([], 0, False),
    ]
    xs = []
    for theta, snr, coh in scenes:
        if theta:
            x = simulate_snapshots(arr, theta, snr, M, rng, coherent=coh)
        else:
            x = (rng.standard_normal((N, M)) + 1j * rng.standard_normal((N, M))) / np.sqrt(2)
        xs.append((theta, x))
        xr, xi = quantize_input(normalize_frame(x)[0])
        frames.append(jacobi_raw(scm_unitary_raw(xr, xi)))
    # Peak-search fallback paths: no local minimum (flat d) and exactly one
    # (signal subspace = one row of B, the second vector zero)
    lam = np.array([5, 4, 3, 2, 1, 0, 0, 0], dtype=np.int64) << 25
    v_flat = np.zeros((N, N), dtype=np.int64)
    v_one = np.zeros((N, N), dtype=np.int64)
    v_one[3, 0] = 1 << 30
    # Minimum on a plateau of equal values (tests d[g] <= d[g+1]) and one local
    # minimum with the global minimum at the grid edge (tests the fallback order)
    v_plateau = np.zeros((N, N), dtype=np.int64)
    v_plateau[3, 0] = 60000
    v_edge = np.zeros((N, N), dtype=np.int64)
    v_edge[1, 0] = 5688218
    v_edge[7, 1] = 50245042
    frames += [(lam, v_flat), (lam, v_one), (lam, v_plateau), (lam, v_edge)]
    return frames, xs


def main():
    os.makedirs(os.path.join(HLS_DIR, "tb"), exist_ok=True)
    write_rom_header(os.path.join(HLS_DIR, "music_rom.h"))
    frames, xs = make_frames()
    write_vectors_header(os.path.join(HLS_DIR, "tb", "music_vectors.h"), frames)
    print(f"{len(frames)} frames written to {os.path.normpath(HLS_DIR)}")
    arr = MimoArray()
    for (theta, x), (d_eig, v) in zip(xs, frames[-len(xs) - 4:-4]):
        a, _ = music_raw(d_eig, v)
        flt = unitary_music_doa(x, arr, 2, GRID, n_sweeps=4)
        print(f"true {theta!s:12} fixed {np.round(angles_deg(a), 4)}  float {np.round(np.sort(flt), 4)}")


if __name__ == "__main__":
    main()
