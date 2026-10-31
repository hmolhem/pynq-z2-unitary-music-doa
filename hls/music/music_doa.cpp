// =====================================================================
// music_doa.cpp -- see music_doa.h
//
// Architecture
//   * Read 72 words, pick the two largest eigenvalues (strict >, lower
//     index wins ties), copy their eigenvectors.
//   * Grid loop, II = 1: 16 products (2 eigenvectors x 8 elements) with
//     the 8 ROM banks read in parallel, two squares, one subtraction.
//   * Peak search over the stored d(g): track the 2 deepest strict local
//     minima and the 2 smallest values overall (fallback).
//   * Parabolic refinement: one integer division per peak.
// =====================================================================
#include "music_doa.h"
#include "music_rom.h"

using namespace mus;

struct cand_t {
    d_t d;
    ap_uint<8> g;
    bool valid;
};

// Keep the two smallest (d, g); new g is always the largest index so far,
// so strict < reproduces sorting by (d, g).
static void insert2(cand_t &c0, cand_t &c1, d_t d, ap_uint<8> g) {
#pragma HLS INLINE
    if (!c0.valid || d < c0.d) {
        c1 = c0;
        c0.d = d; c0.g = g; c0.valid = true;
    } else if (!c1.valid || d < c1.d) {
        c1.d = d; c1.g = g; c1.valid = true;
    }
}

static ang_t refine(const d_t D[G], ap_uint<8> g) {
#pragma HLS INLINE off
    ap_int<40> delta = 0;
    if (g > 0 && g < G - 1) {
        const ap_int<36> y0 = D[g - 1], y1 = D[g], y2 = D[g + 1];
        const ap_int<36> den = y0 - 2 * y1 + y2;
        if (den > 0) {
            const ap_int<36> num = y0 - y2;
            const ap_uint<52> mag = (ap_uint<52>)(num < 0 ? (ap_int<36>)(-num) : num) << ANG_FRAC;
            const ap_uint<38> div = (ap_uint<38>)(den * 2);
            const ap_uint<52> q = mag / div;
            delta = (num < 0) ? (ap_int<40>)(-(ap_int<53>)q) : (ap_int<40>)q;
        }
    }
    return (ang_t)(((ap_int<40>)((int)g - GRID_OFFSET) << ANG_FRAC) + delta);
}

void music_doa(hls::stream<axis_t> &e_in, hls::stream<axis_t> &d_out) {
#pragma HLS INTERFACE mode=axis port=e_in
#pragma HLS INTERFACE mode=axis port=d_out
#pragma HLS INTERFACE mode=s_axilite port=return bundle=control
#pragma HLS ARRAY_PARTITION variable=B_ROM type=complete dim=1

    lam_t lam[N];
    v_t V[N][N];
#pragma HLS ARRAY_PARTITION variable=lam type=complete
#pragma HLS ARRAY_PARTITION variable=V type=complete dim=0

Read_Loop:
    for (int i = 0; i < N_IN; i++) {
#pragma HLS PIPELINE II=1
        const ap_int<32> w = (ap_int<32>)e_in.read().data;
        if (i < N) lam[i] = w;
        else V[(i - N) / N][(i - N) % N] = w;
    }

    // Two largest eigenvalues: strict >, so the lower index wins ties
    int i0 = -1, i1 = -1;
Select_Loop:
    for (int i = 0; i < N; i++) {
#pragma HLS UNROLL
        if (i0 < 0 || lam[i] > lam[i0]) {
            i1 = i0;
            i0 = i;
        } else if (i1 < 0 || lam[i] > lam[i1]) {
            i1 = i;
        }
    }
    v_t E[K][N];
#pragma HLS ARRAY_PARTITION variable=E type=complete dim=0
Copy_Loop:
    for (int n = 0; n < N; n++) {
#pragma HLS UNROLL
        E[0][n] = V[n][i0];
        E[1][n] = V[n][i1];
    }

    // MUSIC denominator on the grid
    d_t D[G];
    const ap_int<64> EIGHT = (ap_int<64>)8 << 58;      // 8 in Q6.58
Grid_Loop:
    for (int g = 0; g < G; g++) {
#pragma HLS PIPELINE II=1
        ap_int<64> s = 0;
        for (int k = 0; k < K; k++) {
            ap_int<60> acc = 0;
            for (int n = 0; n < N; n++) {
                acc += (ap_int<60>)((ap_int<57>)E[k][n] * (b_t)B_ROM[n][g]);
            }
            const p_t p = (p_t)((acc + ((ap_int<60>)1 << 22)) >> 23);   // Q3.29
            s += (ap_int<64>)p * p;                                       // Q6.58
        }
        D[g] = (d_t)(((ap_int<66>)EIGHT - s + ((ap_int<66>)1 << 30)) >> 31);  // Q5.27
    }

    // Peak search: deepest strict local minima, smallest values as fallback
    cand_t m0 = {0, 0, false}, m1 = {0, 0, false};
    cand_t o0 = {0, 0, false}, o1 = {0, 0, false};
    d_t prev = 0, cur = D[0];
Peak_Loop:
    for (int g = 0; g < G; g++) {
#pragma HLS PIPELINE II=1
        const d_t next = (g < G - 1) ? D[g + 1] : (d_t)0;
        insert2(o0, o1, cur, g);
        if (g > 0 && g < G - 1 && cur < prev && cur <= next) insert2(m0, m1, cur, g);
        prev = cur;
        cur = next;
    }
    ap_uint<8> g0, g1;
    if (m1.valid) {
        g0 = m0.g; g1 = m1.g;
    } else if (m0.valid) {
        g0 = m0.g; g1 = (o0.g != m0.g) ? o0.g : o1.g;
    } else {
        g0 = o0.g; g1 = o1.g;
    }

    ang_t a0 = refine(D, g0);
    ang_t a1 = refine(D, g1);
    if (a1 < a0) {
        const ang_t t = a0;
        a0 = a1;
        a1 = t;
    }

    // Two angles, then the denominator; TLAST on the last beat
Out_Loop:
    for (int i = 0; i < N_OUT; i++) {
#pragma HLS PIPELINE II=1
        axis_t beat;
        const ang_t a = (i == 0) ? a0 : a1;
        beat.data = (i < K) ? (ap_uint<32>)a : (ap_uint<32>)D[i - K];
        beat.keep = -1;
        beat.strb = -1;
        beat.last = (i == N_OUT - 1);
        d_out.write(beat);
    }
}
