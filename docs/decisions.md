# Design decisions

| Date | Decision | Reason |
|---|---|---|
| 2026-10-13 | 2 Tx x 4 Rx colocated MIMO, 8-element virtual ULA, centred positions | Filled ULA; centring makes the steering vector conjugate-centro-symmetric, which the unitary transform requires |
| 2026-10-13 | Real-valued (unitary) formulation instead of complex MUSIC | Half the SCM multipliers, real Jacobi EVD, real ROM steering table, coherent-source resolution through forward-backward averaging |
| 2026-10-13 | Cyclic Jacobi with a fixed sweep count | Deterministic hardware latency |
| 2026-10-13 | 4 Jacobi sweeps | Golden model: off-diagonal norm hits the fixed-point floor after sweep 4 |
| 2026-10-13 | MUSIC through the signal subspace: d(theta) = N - sum_k (e_k^T b)^2 | Needs only K eigenvectors and no division; peaks are minima of d |
| 2026-10-13 | Frame scaled on the ARM so every component is in (-1, 1) | The scale cancels in MUSIC; fixes the input range for fixed point |
| 2026-10-13 | Generated Vivado/HLS files are not committed; bitstreams go to Releases | Reproducible rebuilds from Tcl, small repository |
| 2026-10-13 | SCM input: one complex sample per 32-bit AXI-Stream word (`[15:0]` re, `[31:16]` im), snapshot-major | Simplest DMA packing; matches the proposal's interface plan |
| 2026-10-13 | SCM computes y = sqrt(2) Q^H x and folds the factor 2 into 1/(2M) = 2^-8 | Unitary transform with adds only; normalisation is a shift |
| 2026-10-13 | Exact fixed-point accumulation (`ap_fixed<50,12>`), single rounding at the output (`ap_fixed<32,5>`, AP_RND/AP_SAT) | Bit-exact against a simple integer model; one-cycle add removes the float recurrence wall |
| 2026-10-13 | Snapshot loop at II = 8 | Throughput is bound by one sample per clock; lets the 72 products share ~9 multipliers |
| 2026-10-13 | C simulation also runs with g++ and Xilinx's open-source ap_types headers (CI) | Kernels are checked on every push without a Vitis licence |
| 2026-10-18 | Jacobi rotation from CORDIC (vectoring for atan2, rotation for cos/sin), 24 iterations each | No square root or division; every step is a shift-add, so the integer model is bit-exact by construction |
| 2026-10-18 | Normalize the CORDIC vectoring inputs to 30 bits | Late in the sweeps a_pq is tiny; normalization keeps the rotation angle at full precision |
| 2026-10-18 | Symmetric update (only k != p, q in the loop; a_pp, a_qq from c^2, s^2, cs; a_pq := 0) | Exact symmetry, fewer multiplies, same as the classical two-sided rotation |
| 2026-10-18 | Jacobi outputs unsorted eigenvalues and the full V | Sorting and subspace selection stay on the ARM in Tier 2; Tier 3 moves them into the PL |
| 2026-10-18 | Tier 2 overlay chains scm_unitary -> jacobi_evd by AXI-Stream, one DMA | One call per frame; R never leaves the PL |
| 2026-10-31 | MUSIC kernel uses d = 8 - sum p_k^2 with ||b||^2 = N = 8 as a constant | Unit-modulus steering vector; no ROM column norms needed |
| 2026-10-31 | Steering ROM in `ap_fixed<25,2>` (Q2.22), generated from Python into `music_rom.h` | One table shared by C and Python; 25 bits fit one DSP input |
| 2026-10-31 | K = 2 fixed at compile time; output = 2 angles (Q16.16 deg) + full d(theta) | Frozen configuration; the spectrum is kept for plots and verification |
| 2026-10-31 | Parabolic refinement with one integer division per peak, truncated toward zero | Exact and reproducible in the integer model |
| 2026-11-03 | Batching through a `batch` register in `music_doa` (TLAST every batch-th frame) and kernel auto-restart | Throughput with one DMA transfer for many frames, no scatter-gather DMA needed |
| 2026-11-03 | AXI Timer captures on the DMA `mm2s_introut` / `s2mm_introut` | PL latency measured on the board in clock cycles, independent of Python |

