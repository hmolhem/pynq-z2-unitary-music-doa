// =====================================================================
// tb_scm_unitary.cpp -- bit-exact testbench for scm_unitary
//
// Vectors come from python/gen_scm_vectors.py (bit-true model
// python/scm_bitexact.py). Every output bit must match.
// Exit code 0 = PASS (required by Vitis C simulation / co-simulation).
// =====================================================================
#include <cstdint>
#include <cstdio>
#include <fstream>
#include <string>
#include <vector>

#include "../scm_unitary.h"

using namespace scm;

static bool open_first(std::ifstream &f, const std::vector<std::string> &names) {
    for (const auto &n : names) {
        f.open(n);
        if (f.is_open()) {
            std::printf("  using %s\n", n.c_str());
            return true;
        }
        f.clear();
    }
    return false;
}

int main(int argc, char **argv) {
    const std::string dir = argc > 1 ? std::string(argv[1]) + "/" : "";
    std::ifstream fin, fout;
    // Vitis copies tb files next to the csim binary; plain g++ runs from hls/scm
    if (!open_first(fin, {dir + "scm_in.txt", "scm_in.txt", "tb/scm_in.txt", "../tb/scm_in.txt"}) ||
        !open_first(fout, {dir + "scm_out.txt", "scm_out.txt", "tb/scm_out.txt", "../tb/scm_out.txt"})) {
        std::printf("ERROR: test vector files not found\n");
        return 2;
    }

    int frames_in = 0, frames_out = 0;
    fin >> frames_in;
    fout >> frames_out;
    if (frames_in != frames_out || frames_in <= 0) {
        std::printf("ERROR: frame count mismatch (%d vs %d)\n", frames_in, frames_out);
        return 2;
    }

    int total_err = 0;
    for (int f = 0; f < frames_in; f++) {
        hls::stream<word_t> x_in;
        for (int i = 0; i < N * M; i++) {
            long re, im;
            fin >> re >> im;
            word_t w;
            w.range(15, 0) = (ap_uint<16>)(uint16_t)(int16_t)re;
            w.range(31, 16) = (ap_uint<16>)(uint16_t)(int16_t)im;
            x_in.write(w);
        }

        r_t R[N][N];
        scm_unitary(x_in, R);

        int err = 0;
        for (int p = 0; p < N; p++) {
            for (int q = 0; q < N; q++) {
                long long expected;
                fout >> expected;
                long long got = (long long)(int32_t)(uint32_t)R[p][q].range().to_uint();
                if (got != expected) {
                    if (err < 5)
                        std::printf("  frame %d R[%d][%d]: got %lld expected %lld\n",
                                    f, p, q, got, expected);
                    err++;
                }
            }
        }
        if (!x_in.empty()) {
            std::printf("  frame %d: %zu words left in stream\n", f, x_in.size());
            err++;
        }
        std::printf("frame %2d: %s (R[0][0] = %.9f)\n", f, err ? "FAIL" : "pass",
                    R[0][0].to_double());
        total_err += err;
    }

    if (total_err == 0) {
        std::printf("PASS: %d frames, all %d outputs bit-exact\n", frames_in, frames_in * N * N);
        return 0;
    }
    std::printf("FAIL: %d mismatches\n", total_err);
    return 1;
}
