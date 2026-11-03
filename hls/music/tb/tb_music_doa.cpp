// =====================================================================
// tb_music_doa.cpp -- bit-exact testbench for the music_doa IP
//
// Vectors are compiled in from music_vectors.h (python/gen_music_vectors.py,
// bit-true model python/music_bitexact.py). Every output bit and the TLAST
// position must match. Exit code 0 = PASS.
// =====================================================================
#include <cstdint>
#include <cstdio>

#include "../music_doa.h"
#include "music_vectors.h"

using namespace mus;

int main() {
    int total_err = 0;

    for (int f = 0; f < MUS_TV_FRAMES; f++) {
        hls::stream<axis_t> e_in("e_in"), d_out("d_out");
        for (int i = 0; i < N_IN; i++) {
            axis_t beat;
            beat.data = (ap_uint<32>)(uint32_t)MUS_TV_IN[f][i];
            beat.keep = -1;
            beat.strb = -1;
            beat.last = (i == N_IN - 1);
            e_in.write(beat);
        }

        music_doa(e_in, d_out, 1);

        int err = 0;
        double ang[K] = {0, 0};
        for (int j = 0; j < N_OUT; j++) {
            if (d_out.empty()) {
                std::printf("  frame %d: output stream ended after %d words\n", f, j);
                err++;
                break;
            }
            axis_t beat = d_out.read();
            int32_t got = (int32_t)(uint32_t)beat.data.to_uint();
            if (j < K) ang[j] = got * (1.0 / (1 << ANG_FRAC));
            if (got != MUS_TV_OUT[f][j]) {
                if (err < 5)
                    std::printf("  frame %d word %d: got %d expected %d\n",
                                f, j, got, MUS_TV_OUT[f][j]);
                err++;
            }
            if ((int)beat.last != (j == N_OUT - 1 ? 1 : 0)) {
                std::printf("  frame %d word %d: wrong TLAST\n", f, j);
                err++;
            }
        }
        if (!e_in.empty() || !d_out.empty()) {
            std::printf("  frame %d: leftover words in streams\n", f);
            err++;
        }
        std::printf("frame %2d: %s (DOA = %9.4f, %9.4f deg)\n", f, err ? "FAIL" : "pass",
                    ang[0], ang[1]);
        total_err += err;
    }

    // Batched packets: 3 frames with batch = 3 -> TLAST only on the very last
    // word, data identical to the single-frame results
    {
        const int B = 3;
        int err = 0;
        for (int f = 0; f < B; f++) {
            hls::stream<axis_t> e_in("e_in_b"), d_out("d_out_b");
            for (int i = 0; i < N_IN; i++) {
                axis_t beat;
                beat.data = (ap_uint<32>)(uint32_t)MUS_TV_IN[f][i];
                beat.keep = -1;
                beat.strb = -1;
                beat.last = (i == N_IN - 1);
                e_in.write(beat);
            }
            music_doa(e_in, d_out, B);
            for (int j = 0; j < N_OUT; j++) {
                axis_t beat = d_out.read();
                if ((int32_t)(uint32_t)beat.data.to_uint() != MUS_TV_OUT[f][j]) err++;
                const int want_last = (f == B - 1 && j == N_OUT - 1) ? 1 : 0;
                if ((int)beat.last != want_last) err++;
            }
        }
        std::printf("batch of %d frames: %s\n", B, err ? "FAIL" : "pass");
        total_err += err;
    }

    if (total_err == 0) {
        std::printf("PASS: %d frames, all %d outputs bit-exact, TLAST correct\n",
                    MUS_TV_FRAMES, MUS_TV_FRAMES * N_OUT);
        return 0;
    }
    std::printf("FAIL: %d mismatches\n", total_err);
    return 1;
}
