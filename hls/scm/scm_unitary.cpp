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
//   * Output: 64 words streamed row-major at II = 1 from the 36 accumulators.
//   * Latency ~ M * N = 1024 cycles + pipeline depth + 64 output beats.
// =====================================================================
#include "scm_unitary.h"

using namespace scm;

// Row-major (p, q) -> upper-triangle accumulator index of (min, max)
static const ap_uint<6> UT_IDX[N * N] = {
     0,  1,  2,  3,  4,  5,  6,  7,
     1,  8,  9, 10, 11, 12, 13, 14,
     2,  9, 15, 16, 17, 18, 19, 20,
     3, 10, 16, 21, 22, 23, 24, 25,
     4, 11, 17, 22, 26, 27, 28, 29,
     5, 12, 18, 23, 27, 30, 31, 32,
     6, 13, 19, 24, 28, 31, 33, 34,
     7, 14, 20, 25, 29, 32, 34, 35};

void scm_unitary(hls::stream<axis_t> &x_in, hls::stream<axis_t> &r_out) {
#pragma HLS INTERFACE mode=axis port=x_in
#pragma HLS INTERFACE mode=axis port=r_out
#pragma HLS INTERFACE mode=s_axilite port=return bundle=control

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
            word_t w = x_in.read().data;
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
    // Full symmetric matrix, row-major, TLAST on the last beat.
Out_Loop:
    for (int i = 0; i < N * N; i++) {
#pragma HLS PIPELINE II=1
        r_t v = acc[UT_IDX[i]] >> LOG2_2M;
        axis_t beat;
        beat.data = v.range();
        beat.keep = -1;
        beat.strb = -1;
        beat.last = (i == N * N - 1);
        r_out.write(beat);
    }
}
