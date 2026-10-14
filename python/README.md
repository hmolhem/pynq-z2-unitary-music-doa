# Golden model: real-valued (unitary) PCA/MUSIC DOA

Bit-traceable Python reference for the PYNQ-Z2 accelerator. Each function maps
to one hardware stage and takes a quantizer hook, so the same code is both the
floating-point reference and the fixed-point word-length model.

| Stage | Function | HW block |
|---|---|---|
| Virtual-array data | `MimoArray`, `simulate_snapshots` | ARM / test vectors |
| Frame scaling | `normalize_frame` | ARM (before DMA) |
| Unitary transform + real SCM | `real_valued_scm` | PL kernel 1 |
| PCA (EVD) | `jacobi_evd` (fixed sweeps) | PL kernel 2 |
| MUSIC denominator | `music_spectrum_signal_subspace` | PL kernel 3 |
| Peak search + refine | `find_peaks` | PL kernel 3 / ARM |

## Run

```bash
python -m pytest -q          # 9 tests
python sweep_rmse.py 200     # Monte Carlo sweep -> results/
```

Requirements: numpy, matplotlib (pytest for tests).

## First results (200 trials/point, N=8, M=128, DOAs -10/5 deg)

- Uncorrelated sources: unitary MUSIC with Jacobi matches complex MUSIC (numpy
  `eigh`); both fixed-point configurations are indistinguishable from float.
- Coherent sources: complex MUSIC resolves the pair in only 13-26 % of trials;
  unitary MUSIC (implicit forward-backward averaging) reaches 93-98 % at
  SNR >= 5 dB.
- Jacobi: 4 sweeps reach the fixed-point quantization floor -> use 4, not 6.
- Even the 12-bit input / 18-bit Jacobi configuration shows no accuracy loss,
  so the word-length DSE should explore narrower formats to find the knee.
