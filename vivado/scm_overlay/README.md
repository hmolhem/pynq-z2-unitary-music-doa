# SCM overlay (Tier 1)

`DDR -> AXI DMA -> scm_unitary (HLS) -> AXI DMA -> DDR`, kernel control on AXI-Lite.

1. Export the HLS IP: `powershell -ExecutionPolicy Bypass -File ..\..\hls\run_hls.ps1 -Kernel scm`
2. Build: `& "C:\AMDXilinx\2025.2\Vivado\bin\vivado.bat" -mode batch -source build_scm_overlay.tcl`
3. Upload `output/scm_overlay.bit`, `output/scm_overlay.hwh` and
   `pynq/notebooks/02_scm_on_board.ipynb` to one Jupyter folder and run all cells.

The notebook was checked end-to-end with the compiled HLS kernel standing in for the board.
