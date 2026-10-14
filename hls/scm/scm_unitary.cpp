// =====================================================================
// scm_unitary.cpp -- see scm_unitary.h
//
// Architecture
//   * One complex sample per clock from the stream -> one snapshot every
//     8 clocks, so the snapshot loop is pipelined at II = N = 8.
//   * Within those 8 clocks the 72 real products (36 entries x 2) can share
//     about 9 multipliers -- the stream rate, not the multipliers, sets
//     the throughput.
//   * Fixed-point accumulation is exact integer addition (1 cycle), so the
//     floating-point recurrence wall of the earlier float design disappears.
//   * Latency ~ M * N = 1024 cycles + pipeline depth + 64 output writes.
// =====================================================================
#include "scm_unitary.h"

using namespace scm;

void scm_unitary(hls::stream<word_t> &x_in, r_t R[N][N]) {
#pragma HLS INTERFACE mode=axis port=x_in
#pragma HLS INTERFACE mode=ap_ctrl_hs port=return

    acc_t acc[N_UT];
#pragma HLS ARRAY_PARTITION variable=acc type=complete

Init_Loop:
    for (int k = 0; k < N_UT; k++) {
#pragma HLS UNROLL
        acc[k] = 0;
    }

Snapshot_Loop:
    for (int m = 0; m < M; m++) {
#pragma HLS PIPELINE II=8
        in_t xr[N], xi[N];
#pragma HLS ARRAY_PARTITION variable=xr type=complete
#pragma HLS ARRAY_PARTITION variable=xi type=complete

    Read_Loop:
        for (int n = 0; n < N; n++) {
            word_t w = x_in.read();
            xr[n].range() = w.range(15, 0);
            xi[n].range() = w.range(31, 16);
        }

        // y = sqrt(2) Q^H x  (adds only)
        //   top    i: x[i] + x[N-1-i]
        //   bottom i: -j (x[i] - x[N-1-i]) = b - j a,  a + jb = x[i] - x[N-1-i]
        y_t yr[N], yi[N];
#pragma HLS ARRAY_PARTITION variable=yr type=complete
#pragma HLS ARRAY_PARTITION variable=yi type=complete
    Unitary_Loop:
        for (int i = 0; i < HALF; i++) {
            yr[i]        = (y_t)xr[i] + (y_t)xr[N - 1 - i];
            yi[i]        = (y_t)xi[i] + (y_t)xi[N - 1 - i];
            yr[HALF + i] = (y_t)xi[i] - (y_t)xi[N - 1 - i];     //  b
            yi[HALF + i] = (y_t)xr[N - 1 - i] - (y_t)xr[i];     // -a
        }

        // Upper-triangle accumulation, k = row-major index of (p, q), q >= p
    Acc_Row:
        for (int p = 0, k = 0; p < N; p++) {
        Acc_Col:
            for (int q = p; q < N; q++, k++) {
                acc[k] += (acc_t)(yr[p] * yr[q]) + (acc_t)(yi[p] * yi[q]);
            }
        }
    }

    // R = acc / (2M): exact shift, then AP_RND / AP_SAT to the output format.
    // Flat loop over the 36 entries; (p, q) come from small constant tables.
    static const ap_uint<3> P_TAB[N_UT] = {
        0,0,0,0,0,0,0,0, 1,1,1,1,1,1,1, 2,2,2,2,2,2, 3,3,3,3,3, 4,4,4,4, 5,5,5, 6,6, 7};
    static const ap_uint<3> Q_TAB[N_UT] = {
        0,1,2,3,4,5,6,7, 1,2,3,4,5,6,7, 2,3,4,5,6,7, 3,4,5,6,7, 4,5,6,7, 5,6,7, 6,7, 7};
Out_Loop:
    for (int k = 0; k < N_UT; k++) {
#pragma HLS PIPELINE II=2
        r_t v = acc[k] >> LOG2_2M;
        R[P_TAB[k]][Q_TAB[k]] = v;
        R[Q_TAB[k]][P_TAB[k]] = v;
    }
}
