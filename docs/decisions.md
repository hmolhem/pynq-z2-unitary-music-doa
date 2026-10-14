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
