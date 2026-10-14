// =====================================================================
// scm_unitary.h -- Unitary transform + real-valued sample covariance
//
//   y = sqrt(2) Q^H x        (adds only; Q = Huarng & Yeh unitary matrix)
//   R = (1/2M) sum_m (Re y Re y^T + Im y Im y^T) = Re{ Q^H Rhat Q }
//
// R is real symmetric; only the 36 upper-triangle entries are accumulated.
// Bit-true reference: python/scm_bitexact.py
// =====================================================================
#ifndef SCM_UNITARY_H
#define SCM_UNITARY_H

#include <ap_fixed.h>
#include <ap_int.h>
#include <hls_stream.h>

namespace scm {

constexpr int N = 8;                     // virtual array elements
constexpr int M = 128;                   // snapshots per frame
constexpr int HALF = N / 2;
constexpr int N_UT = N * (N + 1) / 2;    // 36 upper-triangle entries
constexpr int LOG2_2M = 8;               // log2(2M); 1/(2M) is a shift

// ---- Number formats ---------------------------------------------------
// Input sample component: (-1, 1), scaled on the ARM before DMA.
typedef ap_fixed<16, 1> in_t;
// y component = sum of two inputs: exact in 17 bits.
typedef ap_fixed<17, 2> y_t;
// Accumulator: exact. Products carry 30 fractional bits; 8 extra
// fractional bits keep the final >> LOG2_2M exact. |sum| <= 1024.
typedef ap_fixed<50, 12> acc_t;
// Output covariance entry: |R| <= 4 by construction.
typedef ap_fixed<32, 5, AP_RND, AP_SAT> r_t;

// One complex sample per 32-bit stream word: [15:0] = re, [31:16] = im.
typedef ap_uint<32> word_t;

}  // namespace scm

// Reads N*M words in snapshot-major order (m outer, n inner) and writes
// the full symmetric N x N matrix.
void scm_unitary(hls::stream<scm::word_t> &x_in, scm::r_t R[scm::N][scm::N]);

#endif  // SCM_UNITARY_H
