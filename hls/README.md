# HLS kernels

| Kernel | Folder | Status |
|---|---|---|
| Unitary transform + real SCM | `scm/` | C simulation bit-exact (g++). Vitis csim / synthesis / co-sim pending |
| Jacobi EVD (PCA) | `jacobi/` | Not started |
| MUSIC denominator + peaks | `music/` | Not started |
| Top-level IP | `top/` | Not started |

## `scm/` -- unitary transform + real-valued SCM

```text
x (8 complex, ap_fixed<16,1>)  ->  y = sqrt(2) Q^H x  (adds only)
R[p][q] = (1/2M) sum_m (Re y_p Re y_q + Im y_p Im y_q)   (36 upper-triangle entries)
```

| Item | Value |
|---|---|
| Interface | `hls::stream<ap_uint<32>>` (AXI4-Stream), one complex sample per word: `[15:0]` re, `[31:16]` im, snapshot-major order |
| Input | `ap_fixed<16,1>` (frame scaled on the ARM so every component is in (-1, 1)) |
| Accumulator | `ap_fixed<50,12>`, exact (no rounding inside the loop) |
| Output | `ap_fixed<32,5,AP_RND,AP_SAT>`, symmetric 8 x 8; \|R\| <= 4 by construction, so saturation never triggers |
| Schedule | snapshot loop pipelined at II = 8 (stream-rate bound); ~9 shared multipliers expected |
| Expected latency | about 1024 + pipeline depth + 72 cycles, i.e. roughly 11 us at 100 MHz (to be confirmed by synthesis) |

The predecessor floating-point SCM kernel needed up to 12,673 cycles because
the floating-point adder recurrence limited the pipeline. Fixed-point
accumulation is a one-cycle integer add, so that limit disappears.

### Verification

Bit-true reference: `python/scm_bitexact.py`. Vectors: `python/gen_scm_vectors.py`
(10 frames: realistic one- and two-source frames, coherent sources, full-scale
positive and negative codes, alternating signs, silence, uniform noise).
The testbench requires every output bit to match.

A mutation check (replacing `AP_RND` by `AP_TRN` in the output format) makes
the testbench fail with 225 mismatches, so it does detect rounding errors.

## Running

**Without Vitis (g++):**

```bash
git clone https://github.com/Xilinx/HLS_arbitrary_Precision_Types
cd hls
make csim-scm AP_INCLUDE=path/to/HLS_arbitrary_Precision_Types/include
```

`common/sim_shim/hls_stream.h` is a minimal stand-in used only by this Makefile.

**Vitis HLS 2025.2:** create an HLS component from `scm/hls_config.cfg`, then
run C simulation, C synthesis and C/RTL co-simulation. The testbench returns 0
on PASS.
