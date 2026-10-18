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

#include <ap_axi_sdata.h>
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
// AXI4-Stream beat with TLAST (what AXI DMA produces and expects)
typedef ap_axiu<32, 0, 0, 0> axis_t;

}  // namespace scm

// Top-level IP for the PYNQ overlay.
//   x_in : AXI4-Stream, N*M words per frame, snapshot-major (m outer,
//          n inner); TLAST is ignored
//   r_out: AXI4-Stream, N*N words per frame, row-major, raw r_t bits,
//          TLAST on the last word (required by AXI DMA S2MM)
//   control: AXI4-Lite (ap_start / ap_done)
void scm_unitary(hls::stream<scm::axis_t> &x_in, hls::stream<scm::axis_t> &r_out);

#endif  // SCM_UNITARY_H
