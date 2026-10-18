// =====================================================================
// tb_scm_unitary.cpp -- bit-exact testbench for the scm_unitary IP
//
// Vectors are compiled in from scm_vectors.h (python/gen_scm_vectors.py,
// bit-true model python/scm_bitexact.py), so C simulation and C/RTL
// co-simulation need no data files. Every output bit and the TLAST
// position must match. Exit code 0 = PASS.
// =====================================================================
#include <cstdint>
#include <cstdio>

#include "../scm_unitary.h"
#include "scm_vectors.h"

using namespace scm;

int main() {
    int total_err = 0;

    for (int f = 0; f < SCM_TV_FRAMES; f++) {
        hls::stream<axis_t> x_in("x_in"), r_out("r_out");
        for (int i = 0; i < N * M; i++) {
            axis_t beat;
            beat.data.range(15, 0) = (ap_uint<16>)(uint16_t)SCM_TV_IN[f][i][0];
            beat.data.range(31, 16) = (ap_uint<16>)(uint16_t)SCM_TV_IN[f][i][1];
            beat.keep = -1;
            beat.strb = -1;
            beat.last = (i == N * M - 1);
            x_in.write(beat);
        }

        scm_unitary(x_in, r_out);

        int err = 0;
        double r00 = 0;
        for (int j = 0; j < N * N; j++) {
            if (r_out.empty()) {
                std::printf("  frame %d: output stream ended after %d words\n", f, j);
                err++;
                break;
            }
            axis_t beat = r_out.read();
            int32_t got = (int32_t)(uint32_t)beat.data.to_uint();
            if (j == 0) r00 = got * (1.0 / (1 << 27));
            if (got != SCM_TV_OUT[f][j]) {
                if (err < 5)
                    std::printf("  frame %d R[%d][%d]: got %d expected %d\n",
                                f, j / N, j % N, got, SCM_TV_OUT[f][j]);
                err++;
            }
            if ((int)beat.last != (j == N * N - 1 ? 1 : 0)) {
                std::printf("  frame %d word %d: wrong TLAST\n", f, j);
                err++;
            }
        }
        if (!x_in.empty() || !r_out.empty()) {
            std::printf("  frame %d: leftover words in streams\n", f);
            err++;
        }
        std::printf("frame %2d: %s (R[0][0] = %.9f)\n", f, err ? "FAIL" : "pass", r00);
        total_err += err;
    }

    if (total_err == 0) {
        std::printf("PASS: %d frames, all %d outputs bit-exact, TLAST correct\n",
                    SCM_TV_FRAMES, SCM_TV_FRAMES * N * N);
        return 0;
    }
    std::printf("FAIL: %d mismatches\n", total_err);
    return 1;
}
