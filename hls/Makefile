# C simulation of the HLS kernels with plain g++ (no Vitis needed).
#
#   make csim-scm        build and run the bit-exact SCM testbench
#   make csim-jacobi     build and run the bit-exact Jacobi EVD testbench
#   make csim            both
#
# Needs the open-source arbitrary-precision headers:
#   git clone https://github.com/Xilinx/HLS_arbitrary_Precision_Types
# and AP_INCLUDE pointing at its include/ folder (default below).
# Vitis HLS itself uses its own headers and hls_config.cfg, not this file.

AP_INCLUDE ?= ../../HLS_arbitrary_Precision_Types/include
CXX        ?= g++
CXXFLAGS   ?= -std=c++14 -O2 -Wall -Wno-unused-label -Wno-unknown-pragmas \
              -Wno-uninitialized -Wno-maybe-uninitialized
INCLUDES    = -isystem $(AP_INCLUDE) -Icommon/sim_shim
BUILD       = build

.PHONY: csim csim-scm csim-jacobi clean

$(BUILD):
	mkdir -p $(BUILD)

$(BUILD)/tb_scm: scm/scm_unitary.cpp scm/tb/tb_scm_unitary.cpp scm/scm_unitary.h scm/tb/scm_vectors.h | $(BUILD)
	$(CXX) $(CXXFLAGS) $(INCLUDES) scm/scm_unitary.cpp scm/tb/tb_scm_unitary.cpp -o $@

csim-scm: $(BUILD)/tb_scm
	./$(BUILD)/tb_scm

$(BUILD)/tb_jacobi: jacobi/jacobi_evd.cpp jacobi/tb/tb_jacobi_evd.cpp jacobi/jacobi_evd.h jacobi/tb/jacobi_vectors.h | $(BUILD)
	$(CXX) $(CXXFLAGS) $(INCLUDES) jacobi/jacobi_evd.cpp jacobi/tb/tb_jacobi_evd.cpp -o $@

csim-jacobi: $(BUILD)/tb_jacobi
	./$(BUILD)/tb_jacobi

csim: csim-scm csim-jacobi

clean:
	rm -rf $(BUILD)
