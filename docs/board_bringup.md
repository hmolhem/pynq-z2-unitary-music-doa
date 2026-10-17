# Board bring-up log and procedure

## Board status

| Date | Item | Result |
|---|---|---|
| 2026-10-17 | Boot from SD (jumper SD, power jumper USB, home router Ethernet) | PASS: DONE LED and LD0-LD3 on, Jupyter at `http://pynq:9090` |
| 2026-10-17 | Image on the loaned card | PYNQ 2.5 (Glasgow), Python 3.6.5, 15 GB root, 8.3 GB free |
| 2026-10-17 | Host tools | Vivado / Vitis HLS 2025.2 (Windows) |

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
