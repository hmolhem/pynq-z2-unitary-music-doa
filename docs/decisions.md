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
