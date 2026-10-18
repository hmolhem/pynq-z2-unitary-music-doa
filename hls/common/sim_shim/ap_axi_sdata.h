// =====================================================================
// Minimal ap_axi_sdata.h stand-in for plain g++ C simulation ONLY.
//
// Vitis HLS ships the real header and never sees this file: it is put on
// the include path only by hls/Makefile. Provides ap_axiu<D,0,0,0> with
// the data / keep / strb / last fields used in this project.
// =====================================================================
#ifndef SIM_SHIM_AP_AXI_SDATA_H
#define SIM_SHIM_AP_AXI_SDATA_H

#include <ap_int.h>

template <int D, int U, int TI, int TD>
struct ap_axiu {
    ap_uint<D> data;
    ap_uint<(D + 7) / 8> keep;
    ap_uint<(D + 7) / 8> strb;
    ap_uint<1> last;
};

#endif  // SIM_SHIM_AP_AXI_SDATA_H
