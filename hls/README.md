# HLS kernels

| Kernel | Folder | Status |
|---|---|---|
| Unitary transform + real SCM | `scm/` | Vitis 2025.2: csim PASS, synthesis, cosim PASS (bit-exact), IP exported |
| Jacobi EVD (PCA) | `jacobi/` | Vitis 2025.2: csim PASS, synthesis, cosim PASS (bit-exact), IP exported; on board bit-exact |
| MUSIC denominator + peaks | `music/` | g++ csim PASS (bit-exact, 25 frames); Vitis run pending |
| Top-level IP | `top/` | Not started |

## `scm/` -- unitary transform + real-valued SCM

```text
x (8 complex, ap_fixed<16,1>)  ->  y = sqrt(2) Q^H x  (adds only)
R[p][q] = (1/2M) sum_m (Re y_p Re y_q + Im y_p Im y_q)   (36 upper-triangle entries)
```

| Item | Value |
|---|---|
| Input | AXI4-Stream `x_in` (`ap_axiu<32,0,0,0>`), 1024 words/frame, one complex sample per word: `[15:0]` re, `[31:16]` im, snapshot-major |
| Output | AXI4-Stream `r_out`, 64 words/frame, full symmetric R row-major as raw `ap_fixed<32,5>` bits, TLAST on word 63 |
| Control | AXI4-Lite `s_axi_control` (ap_start / ap_done at offset 0x00) |
| Sample format | `ap_fixed<16,1>` (frame scaled on the ARM so every component is in (-1, 1)) |
| Accumulator | `ap_fixed<50,12>`, exact (no rounding inside the loop) |
| Output | `ap_fixed<32,5,AP_RND,AP_SAT>`, symmetric 8 x 8; \|R\| <= 4 by construction, so saturation never triggers |
| Schedule | snapshot loop pipelined, II = 8 achieved (stream-rate bound), iteration latency 17 |
| Latency | 1106 cycles = 11.06 us at 100 MHz (synthesis); 1104 cycles measured in co-simulation |

### Vitis HLS 2025.2 results (`scm/reports/`)

| Metric | D5 float SCM (predecessor) | Unitary fixed-point SCM |
|---|---:|---:|
| Latency (cycles) | up to 12,673 | **1,106** (cosim 1,104) |
| Estimated clock (target 10 ns, 2.7 ns uncertainty) | 8.638 ns, slack -1.34 ns | **6.847 ns, slack +0.45 ns** |
| DSP | 24 | 72 |
| LUT | 11,812 | 3,973 |
| FF | 11,655 | 5,748 |
| BRAM | 0 | 0 |
| C/RTL co-simulation | PASS (1 static frame) | PASS (10 frames, bit-exact) |

11.5x lower latency, timing met, a third of the LUTs. HLS did **not** share multipliers
across the 8-cycle initiation interval: all 72 products got their own DSP48. Limiting the
multiplier count (`ALLOCATION` / `BIND_OP`) is the next DSE point if DSPs are needed for the
Jacobi and MUSIC kernels.

The predecessor floating-point SCM kernel needed up to 12,673 cycles because
the floating-point adder recurrence limited the pipeline. Fixed-point
accumulation is a one-cycle integer add, so that limit disappears.

### Verification

Bit-true reference: `python/scm_bitexact.py`. Vectors: `python/gen_scm_vectors.py`
writes `scm/tb/scm_vectors.h`, compiled into the testbench so csim and cosim need no data files
(10 frames: realistic one- and two-source frames, coherent sources, full-scale
positive and negative codes, alternating signs, silence, uniform noise).
The testbench requires every output bit and the TLAST position to match.

A mutation check (replacing `AP_RND` by `AP_TRN` in the output format) makes
the testbench fail with 225 mismatches, so it does detect rounding errors.

## `jacobi/` -- cyclic Jacobi EVD (PCA), CORDIC rotations

```text
for 4 sweeps, for (p, q) in cyclic-by-row order (28 pairs):
    phi   = atan2(2 a_pq, a_qq - a_pp)      CORDIC vectoring, inputs normalized, 24 steps
    (c, s) = cos/sin(phi / 2)               CORDIC rotation, gain precompensated, 24 steps
    A <- J^T A J  (rows/columns p, q; a_pq set to 0),  V <- V J
```

No square root and no division; the only multipliers are in the A and V updates.

| Item | Value |
|---|---|
| Input | AXI4-Stream `r_in`, 64 words: R row-major, raw `ap_fixed<32,5>` (the `scm_unitary` output) |
| Output | AXI4-Stream `e_out`, 72 words: 8 eigenvalues (raw Q7.25), then V row-major (raw Q2.30, column j = eigenvector j), TLAST on word 71; not sorted |
| Control | AXI4-Lite `s_axi_control` |
| Formats | A `ap_fixed<32,7>` (\|a\| <= 32), V, c, s `ap_fixed<32,2>`, angle 28 fractional bits, CORDIC registers 34 bits |
| Rounding | every product rounded once (AP_RND, `(x + 2^29) >> 30`); diagonal from c^2, s^2, cs |
| Accuracy (model) | max \|eig - eigh\| = 4.4e-6 (2.8e-7 of lambda_max), \|V^T V - I\| < 3e-7 |

### Vitis HLS 2025.2 results (`jacobi/reports/`)

| Metric | Value |
|---|---|
| Latency, synthesis | 6,649 - 10,121 cycles (66.5 - 101.2 us) |
| Latency, co-simulation | min 6,199 / avg 9,061 / max 9,447 cycles, PASS bit-exact (14 frames) |
| Estimated clock | 9.609 ns (target 10 ns) |
| DSP / LUT / FF / BRAM | 48 / 13,209 / 11,189 / 0 |

Per rotation: CORDIC vectoring up to 33 cycles, rotation 26, update loop 16 (II = 1), 58 - 89
cycles in total; 112 rotations.

Verification: `python/jacobi_bitexact.py` (bit-true model), `python/gen_jacobi_vectors.py`
(14 frames: the R matrices of the 10 SCM test frames, so Tier 1 -> Tier 2 is covered end to end,
plus diagonal, equal-diagonal theta = pi/4, negative off-diagonal and near-full-scale matrices).
Mutation check: replacing rounding by truncation gives 991 mismatches.

End to end (`python/sweep_tier2_chain.py`, 200 trials per point, sources at -10/5 deg): the
bit-exact chain (fixed-point SCM + Jacobi, MUSIC in float) has the same RMSE and success rate as
the floating-point chain at every SNR from -10 to 20 dB, uncorrelated and coherent
(`python/results/tier2_chain_vs_float.csv`).

## `music/` -- real MUSIC spectrum and peak search (Tier 3)

```text
E_s    = eigenvectors of the 2 largest eigenvalues (strict >, lower index wins ties)
p_k(g) = e_k^T b(g)                 b(g) = Q^H a(theta_g) from an 8 x 181 ROM (music_rom.h)
d(g)   = 8 - p_1(g)^2 - p_2(g)^2     ||b(g)||^2 = N = 8 exactly
peaks  = 2 deepest strict local minima (d[g] < d[g-1], d[g] <= d[g+1]); smallest d as fallback
angle  = (g - 90) + (d[g-1] - d[g+1]) / (2 (d[g-1] - 2 d[g] + d[g+1]))   one division per peak
```

| Item | Value |
|---|---|
| Input | AXI4-Stream `e_in`, 72 words (the `jacobi_evd` output) |
| Output | AXI4-Stream `d_out`, 183 words per frame: 2 angles (raw Q16.16 degrees, ascending), then d(0..180) (raw Q5.27) |
| Batching | AXI-Lite register `batch`: TLAST only on the last word of every `batch`-th frame (0 or 1 = every frame), so with auto-restart one DMA transfer carries many frames |
| Formats | ROM `ap_fixed<25,2>`, projection Q3.29 (one rounding), d Q5.27 (one rounding) |
| Schedule | grid loop II = 1 with the 8 ROM banks read in parallel (16 products per angle), then a 181-cycle peak search |

Verification: `python/music_bitexact.py`, `python/gen_music_vectors.py` (25 frames: the Jacobi
outputs of the 14 Jacobi test matrices, realistic frames including endfire, single, close and
coherent sources and pure noise, and four crafted inputs for the peak-search corner cases:
no local minimum, one local minimum, a minimum on a plateau of equal values, and one minimum
with the global minimum at the grid edge). Six mutations (projection and denominator rounding,
`<=` vs `<` in the minimum test, fallback order, eigenvalue tie rule, output order) all fail
the testbench.

End to end (`python/sweep_tier3_chain.py`, 200 trials per point): the whole estimator in fixed
point has the same RMSE and resolution probability as floating point at every SNR from -10 to
20 dB, uncorrelated and coherent (`python/results/tier3_chain_vs_float.csv`).

## Design-space variants (`dse/`, synthesis only)

| Variant | Change | Question |
|---|---|---|
| `dse/scm_mul9` | `ALLOCATION mul limit=9` in the SCM snapshot loop | Can the 72 DSPs be shared over the II = 8 interval? |
| `dse/jac_cordic16`, `dse/jac_cordic20` | 16 / 20 instead of 24 CORDIC iterations | Latency and resources vs accuracy (`python/dse_cordic.py`) |

Run all three: `powershell -ExecutionPolicy Bypass -File run_dse.ps1`.

## Running

**Without Vitis (g++):**

```bash
git clone https://github.com/Xilinx/HLS_arbitrary_Precision_Types
cd hls
make csim AP_INCLUDE=path/to/HLS_arbitrary_Precision_Types/include   # both kernels
```

`common/sim_shim/hls_stream.h` is a minimal stand-in used only by this Makefile.

**Vitis HLS 2025.2 (Windows, command line):**

```powershell
cd C:\MyDocument\pynq-z2-unitary-music-doa\hls
powershell -ExecutionPolicy Bypass -File run_hls.ps1 -Kernel scm
powershell -ExecutionPolicy Bypass -File run_hls.ps1 -Kernel jacobi
powershell -ExecutionPolicy Bypass -File run_hls.ps1 -Kernel music
```

Runs C simulation, C synthesis, co-simulation and IP export in `scm/work/`, and copies the
synthesis and co-simulation reports to `scm/reports/`. Single steps: `-Steps csim,synth`.
