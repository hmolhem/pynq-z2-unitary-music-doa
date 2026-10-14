// =====================================================================
// Minimal hls::stream stand-in for plain g++ C simulation ONLY.
//
// Vitis HLS ships its own hls_stream.h and never sees this file: it is
// put on the include path only by hls/Makefile (csim without Vitis).
// Supports the subset used in this project: read(), write(), empty(),
// size(), and the >> / << operators.
// =====================================================================
#ifndef SIM_SHIM_HLS_STREAM_H
#define SIM_SHIM_HLS_STREAM_H

#include <cstdio>
#include <cstdlib>
#include <deque>

namespace hls {

template <typename T>
class stream {
public:
    stream() = default;
    explicit stream(const char *) {}

    T read() {
        if (q_.empty()) {
            std::fprintf(stderr, "hls::stream shim: read from empty stream\n");
            std::abort();
        }
        T v = q_.front();
        q_.pop_front();
        return v;
    }
    void read(T &v) { v = read(); }
    void write(const T &v) { q_.push_back(v); }
    bool empty() const { return q_.empty(); }
    std::size_t size() const { return q_.size(); }
    void operator>>(T &v) { v = read(); }
    void operator<<(const T &v) { write(v); }

private:
    std::deque<T> q_;
};

}  // namespace hls

#endif  // SIM_SHIM_HLS_STREAM_H
