# =====================================================================
# build_dma_loopback.tcl -- PYNQ-Z2 bring-up overlay: AXI DMA loopback
#
#   Zynq PS --(HP0)--> AXI DMA MM2S --AXIS--> FIFO --AXIS--> AXI DMA S2MM --(HP0)--> DDR
#
# Purpose: prove the ARM <-> FPGA data path (PYNQ allocate + AXI DMA)
# with the same tool version that will build the DOA accelerator.
#
# Usage (Vivado 2025.2 Tcl Shell, from any directory):
#     source <repo>/vivado/dma_loopback/build_dma_loopback.tcl
# or
#     vivado -mode batch -source build_dma_loopback.tcl
#
# Outputs (next to this script):
#     output/dma_loopback.bit   output/dma_loopback.hwh
#     output/utilization.rpt    output/timing_summary.rpt
# =====================================================================

set script_dir [file dirname [file normalize [info script]]]
set proj_name  dma_loopback
set proj_dir   [file join $script_dir build]
set out_dir    [file join $script_dir output]
set part       xc7z020clg400-1
set bd_name    $proj_name

# ---------------------------------------------------------------------
# 1. PYNQ-Z2 board files (needed for the DDR / MIO preset of the PS)
# ---------------------------------------------------------------------
proc find_pynq_z2_board {} {
    return [lindex [get_board_parts -quiet -latest_file_version *pynq-z2*] 0]
}

# Boards installed from the Vivado Store live in the per-user xhub folder, which
# batch-mode Vivado does not search by default: add it before looking.
set xhub_boards [file join $::env(APPDATA) Xilinx Vivado [version -short] xhub board_store xilinx_board_store]
if {[file isdirectory $xhub_boards]} {
    set_param board.repoPaths [list $xhub_boards]
}
set board_part [find_pynq_z2_board]
if {$board_part eq ""} {
    puts "INFO: PYNQ-Z2 board files not found, trying the Vivado board store (takes ~1 min)..."
    if {[catch {
        set store [xhub::get_xstores xilinx_board_store]
        xhub::refresh_catalog $store
        set item [xhub::get_xitems -quiet *pynq-z2*]
        if {$item ne ""} {
            xhub::install $item
            set_param board.repoPaths [get_property LOCAL_ROOT_DIR $store]
        }
    } err]} {
        puts "WARNING: board store access failed: $err"
    }
    set board_part [find_pynq_z2_board]
}
if {$board_part eq ""} {
    error "PYNQ-Z2 board files are not installed.\
           In the Vivado GUI: Tools > Vivado Store > Boards, search 'pynq-z2', Install,\
           then run this script again."
}
puts "INFO: using board part $board_part"

# Latest available version of an IP, so the script survives version bumps
proc ip_vlnv {name} {
    set defs [lsort -dictionary [get_ipdefs -all -filter "NAME == $name && VLNV =~ xilinx.com:ip:*"]]
    if {[llength $defs] == 0} { error "IP $name not found in the catalog" }
    return [lindex $defs end]
}

# ---------------------------------------------------------------------
# 2. Project and block design
# ---------------------------------------------------------------------
file mkdir $out_dir
create_project $proj_name $proj_dir -part $part -force
set_property board_part $board_part [current_project]
create_bd_design $bd_name

# Zynq PS with the PYNQ-Z2 preset, 100 MHz fabric clock, HP0 slave port
set ps [create_bd_cell -type ip -vlnv [ip_vlnv processing_system7] processing_system7_0]
apply_bd_automation -rule xilinx.com:bd_rule:processing_system7 \
    -config {make_external "FIXED_IO, DDR" apply_board_preset "1" Master "Disable" Slave "Disable"} $ps
set_property -dict [list \
    CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ {100} \
    CONFIG.PCW_USE_S_AXI_HP0 {1} \
    CONFIG.PCW_USE_M_AXI_GP0 {1} \
] $ps

# AXI DMA: simple mode (no scatter-gather), 32-bit stream, 26-bit length register
set dma [create_bd_cell -type ip -vlnv [ip_vlnv axi_dma] axi_dma_0]
set_property -dict [list \
    CONFIG.c_include_sg {0} \
    CONFIG.c_sg_length_width {26} \
    CONFIG.c_m_axis_mm2s_tdata_width {32} \
    CONFIG.c_mm2s_burst_size {16} \
    CONFIG.c_s2mm_burst_size {16} \
] $dma

# Loopback FIFO between MM2S and S2MM
set fifo [create_bd_cell -type ip -vlnv [ip_vlnv axis_data_fifo] axis_data_fifo_0]
set_property -dict [list CONFIG.FIFO_DEPTH {1024}] $fifo

# AXI connections through the connection automation
apply_bd_automation -rule xilinx.com:bd_rule:axi4 -config { \
    Clk_master {Auto} Clk_slave {Auto} Clk_xbar {Auto} \
    Master {/processing_system7_0/M_AXI_GP0} Slave {/axi_dma_0/S_AXI_LITE} \
    ddr_seg {Auto} intc_ip {New AXI Interconnect} master_apm {0}} \
    [get_bd_intf_pins axi_dma_0/S_AXI_LITE]
apply_bd_automation -rule xilinx.com:bd_rule:axi4 -config { \
    Clk_master {Auto} Clk_slave {Auto} Clk_xbar {Auto} \
    Master {/axi_dma_0/M_AXI_MM2S} Slave {/processing_system7_0/S_AXI_HP0} \
    ddr_seg {Auto} intc_ip {New AXI SmartConnect} master_apm {0}} \
    [get_bd_intf_pins processing_system7_0/S_AXI_HP0]
apply_bd_automation -rule xilinx.com:bd_rule:axi4 -config { \
    Clk_master {Auto} Clk_slave {Auto} Clk_xbar {Auto} \
    Master {/axi_dma_0/M_AXI_S2MM} Slave {/processing_system7_0/S_AXI_HP0} \
    ddr_seg {Auto} intc_ip {Auto} master_apm {0}} \
    [get_bd_intf_pins axi_dma_0/M_AXI_S2MM]

# Stream loop: MM2S -> FIFO -> S2MM
connect_bd_intf_net [get_bd_intf_pins axi_dma_0/M_AXIS_MM2S] [get_bd_intf_pins axis_data_fifo_0/S_AXIS]
connect_bd_intf_net [get_bd_intf_pins axis_data_fifo_0/M_AXIS] [get_bd_intf_pins axi_dma_0/S_AXIS_S2MM]

# FIFO clock and reset from the same domain as the DMA
set rst [lindex [get_bd_cells -filter {VLNV =~ *proc_sys_reset*}] 0]
connect_bd_net [get_bd_pins processing_system7_0/FCLK_CLK0] [get_bd_pins axis_data_fifo_0/s_axis_aclk]
connect_bd_net [get_bd_pins $rst/peripheral_aresetn] [get_bd_pins axis_data_fifo_0/s_axis_aresetn]

assign_bd_address
validate_bd_design
save_bd_design

# ---------------------------------------------------------------------
# 3. Synthesis, implementation, bitstream
# ---------------------------------------------------------------------
set bd_file [get_files $bd_name.bd]
generate_target all $bd_file
set wrapper [make_wrapper -files $bd_file -top]
add_files -norecurse $wrapper
set_property top ${bd_name}_wrapper [current_fileset]
update_compile_order -fileset sources_1

launch_runs impl_1 -to_step write_bitstream -jobs 4
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {
    error "Implementation failed: see $proj_dir/$proj_name.runs/impl_1/runme.log"
}

# ---------------------------------------------------------------------
# 4. Collect the overlay files (.bit and .hwh must share a base name)
# ---------------------------------------------------------------------
set bit [lindex [glob -nocomplain [file join $proj_dir $proj_name.runs impl_1 *.bit]] 0]
set hwh [lindex [glob -nocomplain [file join $proj_dir $proj_name.gen sources_1 bd $bd_name hw_handoff *.hwh]] 0]
if {$hwh eq ""} {
    set hwh [lindex [glob -nocomplain [file join $proj_dir $proj_name.srcs sources_1 bd $bd_name hw_handoff *.hwh]] 0]
}
file copy -force $bit [file join $out_dir $proj_name.bit]
file copy -force $hwh [file join $out_dir $proj_name.hwh]

open_run impl_1
report_utilization    -file [file join $out_dir utilization.rpt]
report_timing_summary -file [file join $out_dir timing_summary.rpt]

set wns [get_property STATS.WNS [get_runs impl_1]]
puts "================================================================"
puts " DONE. Overlay files:"
puts "   [file join $out_dir $proj_name.bit]"
puts "   [file join $out_dir $proj_name.hwh]"
puts " Worst negative slack (WNS): $wns ns  (must be >= 0)"
puts "================================================================"
