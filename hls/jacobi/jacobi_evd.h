// =====================================================================
// jacobi_evd.h -- Fixed-point cyclic Jacobi EVD (PCA) of the 8x8 real
//                 covariance from scm_unitary (Tier 2)
//
//   phi    = atan2(2 a_pq, a_qq - a_pp)   CORDIC vectoring (shift-add)
//   theta  = phi / 2,  (c, s) = (cos, sin) theta   CORDIC rotation
//   A <- J^T A J,  V <- V J               multipliers only here
//
// No square root and no division. Fixed sweep count = fixed latency.
// Bit-true reference: python/jacobi_bitexact.py
// =====================================================================
#ifndef JACOBI_EVD_H
#define JACOBI_EVD_H

#include <ap_axi_sdata.h>
#include <ap_int.h>
#include <hls_stream.h>

namespace jac {

constexpr int N = 8;
constexpr int N_PAIRS = N * (N - 1) / 2;   // 28 rotations per sweep
constexpr int N_SWEEPS = 4;
constexpr int N_OUT = N + N * N;           // eigenvalues, then V row-major
constexpr int N_CORDIC = 24;
constexpr int NORM_BITS = 30;

// All values are raw two's-complement integers with a fixed binary point
// (the comment gives the equivalent ap_fixed type). Explicit integers keep
// the rounding identical to the Python model.
typedef ap_int<32> r_t;     // input R      ap_fixed<32,5>  Q5.27
typedef ap_int<32> a_t;     // matrix A     ap_fixed<32,7>  Q7.25
typedef ap_int<32> v_t;     // V, c, s      ap_fixed<32,2>  Q2.30
typedef ap_int<32> ang_t;   // angle        ap_fixed<32,4>  rad, 28 frac bits
typedef ap_int<34> cr_t;    // CORDIC x, y registers
typedef ap_int<66> prod_t;  // c*a - s*b before rounding
typedef ap_int<68> diag_t;  // c^2 a - 2cs b + s^2 d before rounding

typedef ap_axiu<32, 0, 0, 0> axis_t;

}  // namespace jac

// Top-level IP.
//   r_in : AXI4-Stream, 64 words, R row-major (raw ap_fixed<32,5>), as
//          produced by scm_unitary; TLAST ignored
//   e_out: AXI4-Stream, 72 words: 8 eigenvalues (raw Q7.25), then V
//          row-major (raw Q2.30; column j = eigenvector j); TLAST on the
//          last word. Eigenvalues are not sorted.
//   control: AXI4-Lite (ap_start / ap_done)
void jacobi_evd(hls::stream<jac::axis_t> &r_in, hls::stream<jac::axis_t> &e_out);

#endif  // JACOBI_EVD_H
