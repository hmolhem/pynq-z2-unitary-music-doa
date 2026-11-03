// =====================================================================
// music_doa.h -- Real-valued MUSIC spectrum and peak search (Tier 3)
//
//   input : jacobi_evd output -- 8 eigenvalues (Q7.25), V row-major (Q2.30)
//   E_s   : eigenvectors of the K = 2 largest eigenvalues
//   d(g)  = 8 - sum_k (e_k^T b(g))^2       g = 0..180 (-90..90 deg)
//   peaks : K deepest strict local minima of d, parabolic refinement
//   output: 2 angles (Q16.16 deg, ascending), then d(0..180) (Q5.27)
//
// b(g) = Q^H a(theta_g) is real; the table is a ROM (music_rom.h).
// Bit-true reference: python/music_bitexact.py
// =====================================================================
#ifndef MUSIC_DOA_H
#define MUSIC_DOA_H

#include <ap_axi_sdata.h>
#include <ap_int.h>
#include <hls_stream.h>

namespace mus {

constexpr int N = 8;
constexpr int K = 2;                 // number of sources (known)
constexpr int G = 181;               // grid points
constexpr int GRID_OFFSET = 90;      // index g <-> angle g - 90 deg
constexpr int N_IN = N + N * N;      // 72 words
constexpr int N_OUT = K + G;         // 183 words
constexpr int ANG_FRAC = 16;

typedef ap_int<32> lam_t;    // eigenvalue   Q7.25
typedef ap_int<32> v_t;      // eigenvector  Q2.30
typedef ap_int<25> b_t;      // steering ROM Q2.22
typedef ap_int<32> p_t;      // projection   Q3.29
typedef ap_int<32> d_t;      // denominator  Q5.27
typedef ap_int<32> ang_t;    // angle        Q16.16 degrees

typedef ap_axiu<32, 0, 0, 0> axis_t;

}  // namespace mus

// Top-level IP.
//   e_in : AXI4-Stream, 72 words from jacobi_evd; TLAST ignored
//   d_out: AXI4-Stream, 183 words per frame: 2 angles, then the MUSIC
//          denominator. TLAST on the last word of every batch-th frame, so
//          several frames can be collected by one DMA transfer.
//   batch: AXI4-Lite register, frames per output packet (0 or 1 = every frame)
//   control: AXI4-Lite (ap_start / ap_done / auto_restart)
void music_doa(hls::stream<mus::axis_t> &e_in, hls::stream<mus::axis_t> &d_out,
               ap_uint<16> batch);

#endif  // MUSIC_DOA_H
