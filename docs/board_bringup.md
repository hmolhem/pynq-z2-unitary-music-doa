# Board bring-up log and procedure

## Board status

| Date | Item | Result |
|---|---|---|
| 2026-10-17 | Boot from SD (jumper SD, power jumper USB, home router Ethernet) | PASS: DONE LED and LD0-LD3 on, Jupyter at `http://pynq:9090` |
| 2026-10-17 | Image on the loaned card | PYNQ 2.5 (Glasgow), Python 3.6.5, 15 GB root, 8.3 GB free |
| 2026-10-17 | Host tools | Vivado / Vitis HLS 2025.2 (Windows), installed in `C:\AMDXilinx` |
| 2026-10-17 | DMA loopback overlay build (Vivado 2025.2, Tcl, first run) | PASS: WNS = +2.422 ns at 100 MHz |
| 2026-10-17 | DMA loopback on PYNQ 2.5 | PASS: counter (1024 words), random (4096 words), DOA-format frame (1024 words) bit-exact |
| 2026-10-17 | Host-observed round trip, one 1024-word frame (200 runs) | median 546.2 us, min 536.7 us, max 1339.6 us |
| 2026-10-17 | SCM overlay (Tier 1), WNS +2.157 ns | PASS: 50/50 frames bit-exact, DOA -10/5 deg recovered (uncorrelated and coherent); see `results/board/` |

**Findings**

- Overlays built with Vivado 2025.2 load and run on PYNQ 2.5: the tool-version risk is retired.
- The 4 KiB transfer itself needs only ~10-20 us at HP-port bandwidth, so ~0.5 ms is dominated by
  the Python/driver call path on the Cortex-A9 (buffer cache maintenance, register polling).
  Consequence for the accelerator: report kernel latency (PL cycle counter) separately from the
  host-observed time, and amortise the per-call cost by streaming several frames per transfer.

PYNQ 2.5 was built with Vivado 2019.1; PYNQ 3.1 (latest, PYNQ-Z2 image available) with
Vivado 2024.1. Plan: keep the loaned card untouched and run PYNQ 3.1 from a second card.
The DMA loopback below is first tried on 2.5 to measure the tool-version risk.

## Step 1 -- AXI DMA loopback

### Build (Windows, Vivado 2025.2)

1. Get the repository: `git clone https://github.com/hmolhem/pynq-z2-unitary-music-doa`
   into a path **without spaces**, e.g. `C:\MyDocument\`.
2. Start menu: open **Vivado 2025.2 Tcl Shell**.
3. Run:
   ```tcl
   cd C:/MyDocument/pynq-z2-unitary-music-doa/vivado/dma_loopback
   source build_dma_loopback.tcl
   ```
   Takes about 10-15 minutes. If it stops with "PYNQ-Z2 board files are not installed",
   open the Vivado GUI, **Tools > Vivado Store > Boards**, search `pynq-z2`, Install, rerun.
4. Result in `vivado/dma_loopback/output/`: `dma_loopback.bit`, `dma_loopback.hwh`,
   utilization and timing reports. The last lines print the WNS (must be >= 0).

### Run on the board

1. In Jupyter (`http://pynq:9090`): **New > Folder**, rename it `dma_loopback`.
2. Open it and **Upload** three files: `dma_loopback.bit`, `dma_loopback.hwh`
   (from `output/`) and `pynq/notebooks/01_dma_loopback.ipynb`.
3. Open the notebook and run all cells. Expected: four PASS lines and a transfer time.
