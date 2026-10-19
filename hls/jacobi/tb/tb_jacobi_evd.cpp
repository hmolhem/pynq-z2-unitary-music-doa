// =====================================================================
// tb_jacobi_evd.cpp -- bit-exact testbench for the jacobi_evd IP
//
// Vectors are compiled in from jacobi_vectors.h (python/gen_jacobi_vectors.py,
// bit-true model python/jacobi_bitexact.py). Every output bit and the TLAST
// position must match. Exit code 0 = PASS.
// =====================================================================
#include <cstdint>
#include <cstdio>

#include "../jacobi_evd.h"
#include "jacobi_vectors.h"

using namespace jac;

int main() {
    int total_err = 0;

    for (int f = 0; f < JAC_TV_FRAMES; f++) {
        hls::stream<axis_t> r_in("r_in"), e_out("e_out");
        for (int i = 0; i < N * N; i++) {
            axis_t beat;
            beat.data = (ap_uint<32>)(uint32_t)JAC_TV_IN[f][i];
            beat.keep = -1;
            beat.strb = -1;
            beat.last = (i == N * N - 1);
            r_in.write(beat);
        }

        jacobi_evd(r_in, e_out);

        int err = 0;
        double lmax = -1e9;
        for (int j = 0; j < N_OUT; j++) {
            if (e_out.empty()) {
                std::printf("  frame %d: output stream ended after %d words\n", f, j);
                err++;
                break;
            }
            axis_t beat = e_out.read();
            int32_t got = (int32_t)(uint32_t)beat.data.to_uint();
            if (j < N && got * (1.0 / (1 << 25)) > lmax) lmax = got * (1.0 / (1 << 25));
            if (got != JAC_TV_OUT[f][j]) {
                if (err < 5)
                    std::printf("  frame %d word %d: got %d expected %d\n",
                                f, j, got, JAC_TV_OUT[f][j]);
                err++;
            }
            if ((int)beat.last != (j == N_OUT - 1 ? 1 : 0)) {
                std::printf("  frame %d word %d: wrong TLAST\n", f, j);
                err++;
            }
        }
        if (!r_in.empty() || !e_out.empty()) {
            std::printf("  frame %d: leftover words in streams\n", f);
            err++;
        }
        std::printf("frame %2d: %s (lambda_max = %.6f)\n", f, err ? "FAIL" : "pass", lmax);
        total_err += err;
    }

    if (total_err == 0) {
        std::printf("PASS: %d frames, all %d outputs bit-exact, TLAST correct\n",
                    JAC_TV_FRAMES, JAC_TV_FRAMES * N_OUT);
        return 0;
    }
    std::printf("FAIL: %d mismatches\n", total_err);
    return 1;
}
