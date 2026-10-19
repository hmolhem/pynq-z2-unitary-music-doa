// =====================================================================
// jacobi_evd.cpp -- see jacobi_evd.h
//
// Architecture (first version: one rotation at a time)
//   * A and V live in registers (complete partition).
//   * Per rotation: CORDIC vectoring (24 shift-add steps) -> theta ->
//     CORDIC rotation (24 steps) -> (c, s) -> 8-iteration update loop at
//     II = 1 (column of A and of V) -> two diagonal entries.
//   * 4 sweeps x 28 rotations = 112 rotations, fixed latency.
// =====================================================================
#include "jacobi_evd.h"

using namespace jac;

// atan(2^-i) with 28 fractional bits
static const ang_t ATAN_TABLE[N_CORDIC] = {
    210828714, 124459457, 65760959, 33381290, 16755422, 8385879,
    4193963,   2097109,   1048571,  524287,   262144,   131072,
    65536,     32768,     16384,    8192,     4096,     2048,
    1024,      512,       256,      128,      64,       32};
static const v_t CORDIC_KINV = 652032874;   // prod 1/sqrt(1+2^-2i), Q2.30

static const ap_uint<3> PAIR_P[N_PAIRS] = {
    0, 0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 5, 5, 6};
static const ap_uint<3> PAIR_Q[N_PAIRS] = {
    1, 2, 3, 4, 5, 6, 7, 2, 3, 4, 5, 6, 7, 3, 4, 5, 6, 7, 4, 5, 6, 7, 5, 6, 7, 6, 7, 7};

// Round half toward +inf, drop 30 bits (AP_RND)
template <int W>
static v_t rnd30(ap_int<W> x) {
#pragma HLS INLINE
    return (v_t)((x + (ap_int<W>(1) << 29)) >> 30);
}

// atan2(y, x) for x >= 0 (angle, 28 fractional bits)
static ang_t cordic_vectoring(cr_t x, cr_t y) {
#pragma HLS INLINE off
    // Normalize: shift both so that max(|x|, |y|) has NORM_BITS bits
    ap_uint<34> ax = (x < 0) ? (ap_uint<34>)(-x) : (ap_uint<34>)x;
    ap_uint<34> ay = (y < 0) ? (ap_uint<34>)(-y) : (ap_uint<34>)y;
    ap_uint<34> m = (ax > ay) ? ax : ay;
    if (m == 0) return 0;
    int len = 0;
Len_Loop:
    for (int i = 0; i < 34; i++) {
#pragma HLS UNROLL
        if (m[i]) len = i + 1;
    }
    int sh = NORM_BITS - len;
    if (sh > 0) {
        x = x << sh;
        y = y << sh;
    } else if (sh < 0) {
        x = x >> (-sh);
        y = y >> (-sh);
    }
    ang_t z = 0;
Vec_Loop:
    for (int i = 0; i < N_CORDIC; i++) {
#pragma HLS PIPELINE II=1
        cr_t xs = x >> i, ys = y >> i;
        if (y >= 0) {
            x = x + ys;
            y = y - xs;
            z = z + ATAN_TABLE[i];
        } else {
            x = x - ys;
            y = y + xs;
            z = z - ATAN_TABLE[i];
        }
    }
    return z;
}

// (cos, sin) theta in Q2.30, |theta| <= pi/4
static void cordic_rotation(ang_t theta, v_t &c, v_t &s) {
#pragma HLS INLINE off
    cr_t x = CORDIC_KINV, y = 0;
    ang_t z = theta;
Rot_Loop:
    for (int i = 0; i < N_CORDIC; i++) {
#pragma HLS PIPELINE II=1
        cr_t xs = x >> i, ys = y >> i;
        if (z >= 0) {
            x = x - ys;
            y = y + xs;
            z = z - ATAN_TABLE[i];
        } else {
            x = x + ys;
            y = y - xs;
            z = z + ATAN_TABLE[i];
        }
    }
    c = (v_t)x;
    s = (v_t)y;
}

void jacobi_evd(hls::stream<axis_t> &r_in, hls::stream<axis_t> &e_out) {
#pragma HLS INTERFACE mode=axis port=r_in
#pragma HLS INTERFACE mode=axis port=e_out
#pragma HLS INTERFACE mode=s_axilite port=return bundle=control

    a_t A[N][N];
    v_t V[N][N];
#pragma HLS ARRAY_PARTITION variable=A type=complete dim=0
#pragma HLS ARRAY_PARTITION variable=V type=complete dim=0

    // R (Q5.27) -> A (Q7.25) with one rounding; V = I
Read_Loop:
    for (int i = 0; i < N * N; i++) {
#pragma HLS PIPELINE II=1
        r_t r = (r_t)r_in.read().data;
        A[i / N][i % N] = (a_t)(((ap_int<34>)r + 2) >> 2);
        V[i / N][i % N] = (i / N == i % N) ? (v_t)(1 << 30) : (v_t)0;
    }

Sweep_Loop:
    for (int sw = 0; sw < N_SWEEPS; sw++) {
    Pair_Loop:
        for (int t = 0; t < N_PAIRS; t++) {
            const int p = PAIR_P[t], q = PAIR_Q[t];
            const a_t app = A[p][p], aqq = A[q][q], apq = A[p][q];

            // Rotation angle: tan(2 theta) = 2 a_pq / (a_qq - a_pp), x >= 0
            cr_t x = (cr_t)aqq - (cr_t)app;
            cr_t y = (cr_t)apq * 2;
            if (x < 0) {
                x = -x;
                y = -y;
            }
            ang_t phi = cordic_vectoring(x, y);
            v_t c, s;
            cordic_rotation(phi >> 1, c, s);

            const v_t c2 = rnd30<64>((ap_int<64>)c * c);
            const v_t s2 = rnd30<64>((ap_int<64>)s * s);
            const v_t cs = rnd30<64>((ap_int<64>)c * s);

        Update_Loop:
            for (int k = 0; k < N; k++) {
#pragma HLS PIPELINE II=1
#pragma HLS DEPENDENCE variable=A type=inter false
#pragma HLS DEPENDENCE variable=V type=inter false
                if (k != p && k != q) {
                    const a_t akp = A[k][p], akq = A[k][q];
                    const a_t nkp = rnd30<66>((prod_t)c * akp - (prod_t)s * akq);
                    const a_t nkq = rnd30<66>((prod_t)s * akp + (prod_t)c * akq);
                    A[k][p] = nkp;
                    A[p][k] = nkp;
                    A[k][q] = nkq;
                    A[q][k] = nkq;
                }
                const v_t vkp = V[k][p], vkq = V[k][q];
                V[k][p] = rnd30<66>((prod_t)c * vkp - (prod_t)s * vkq);
                V[k][q] = rnd30<66>((prod_t)s * vkp + (prod_t)c * vkq);
            }

            const diag_t two_cs_apq = (diag_t)((prod_t)cs * apq) * 2;
            A[p][p] = rnd30<68>((diag_t)((prod_t)c2 * app) - two_cs_apq + (diag_t)((prod_t)s2 * aqq));
            A[q][q] = rnd30<68>((diag_t)((prod_t)s2 * app) + two_cs_apq + (diag_t)((prod_t)c2 * aqq));
            A[p][q] = 0;
            A[q][p] = 0;
        }
    }

    // Eigenvalues (diagonal), then V row-major; TLAST on the last beat
Out_Loop:
    for (int i = 0; i < N_OUT; i++) {
#pragma HLS PIPELINE II=1
        axis_t beat;
        const int j = i - N;
        beat.data = (i < N) ? (ap_uint<32>)A[i][i] : (ap_uint<32>)V[j / N][j % N];
        beat.keep = -1;
        beat.strb = -1;
        beat.last = (i == N_OUT - 1);
        e_out.write(beat);
    }
}
