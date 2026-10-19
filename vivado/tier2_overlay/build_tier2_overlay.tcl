# =====================================================================
# build_tier2_overlay.tcl -- PYNQ-Z2 overlay: Tier 2 (covariance + PCA on the PL)
#
#   DDR --(HP0)--> AXI DMA MM2S --AXIS--> scm_unitary --AXIS--> jacobi_evd --AXIS--> AXI DMA S2MM --(HP0)--> DDR
#        1024 words in (x)                         64 words (R)               72 words out (eigenvalues, V)
#   Both kernels are started through their AXI-Lite control registers on GP0.
#
# Prerequisite: both HLS IPs are exported first:
#     powershell -ExecutionPolicy Bypass -File hls/run_hls.ps1 -Kernel scm
#     powershell -ExecutionPolicy Bypass -File hls/run_hls.ps1 -Kernel jacobi
#
# Usage (from this folder):
#     vivado -mode batch -source build_tier2_overlay.tcl
#
# Outputs (next to this script):
#     output/tier2_overlay.bit    output/tier2_overlay.hwh
#     output/utilization.rpt    output/timing_summary.rpt
# =====================================================================

set script_dir [file dirname [file normalize [info script]]]
set proj_name  tier2_overlay
set hls_dir    [file normalize [file join $script_dir .. .. hls]]
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

# HLS IP repository: the folder holding the exported component.xml
proc find_component {dir} {
    foreach f [glob -nocomplain -directory $dir -types f component.xml] { return [file dirname $f] }
    foreach d [glob -nocomplain -directory $dir -types d *] {
        set r [find_component $d]
        if {$r ne ""} { return $r }
    }
    return ""
}
set ip_repos {}
foreach k {scm jacobi} {
    set r [find_component [file join $hls_dir $k work]]
    if {$r eq ""} {
        error "Exported HLS IP not found under [file join $hls_dir $k work].\
               Run first: powershell -ExecutionPolicy Bypass -File hls/run_hls.ps1 -Kernel $k"
    }
    puts "INFO: HLS IP repository $r"
    lappend ip_repos $r
}

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
set_property ip_repo_paths $ip_repos [current_project]
update_ip_catalog
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

# HLS covariance kernel
set scm_def [lindex [get_ipdefs -all -filter {NAME == scm_unitary}] end]
if {$scm_def eq ""} { error "scm_unitary not in the IP catalog (check $ip_repos)" }
set scm [create_bd_cell -type ip -vlnv $scm_def scm_unitary_0]

# HLS Jacobi EVD kernel
set jac_def [lindex [get_ipdefs -all -filter {NAME == jacobi_evd}] end]
if {$jac_def eq ""} { error "jacobi_evd not in the IP catalog (check $ip_repos)" }
set jac [create_bd_cell -type ip -vlnv $jac_def jacobi_evd_0]

# AXI connections through the connection automation
apply_bd_automation -rule xilinx.com:bd_rule:axi4 -config { \
    Clk_master {Auto} Clk_slave {Auto} Clk_xbar {Auto} \
    Master {/processing_system7_0/M_AXI_GP0} Slave {/axi_dma_0/S_AXI_LITE} \
    ddr_seg {Auto} intc_ip {New AXI Interconnect} master_apm {0}} \
    [get_bd_intf_pins axi_dma_0/S_AXI_LITE]
apply_bd_automation -rule xilinx.com:bd_rule:axi4 -config { \
    Clk_master {Auto} Clk_slave {Auto} Clk_xbar {Auto} \
    Master {/processing_system7_0/M_AXI_GP0} Slave {/scm_unitary_0/s_axi_control} \
    ddr_seg {Auto} intc_ip {Auto} master_apm {0}} \
    [get_bd_intf_pins scm_unitary_0/s_axi_control]
apply_bd_automation -rule xilinx.com:bd_rule:axi4 -config { \
    Clk_master {Auto} Clk_slave {Auto} Clk_xbar {Auto} \
    Master {/processing_system7_0/M_AXI_GP0} Slave {/jacobi_evd_0/s_axi_control} \
    ddr_seg {Auto} intc_ip {Auto} master_apm {0}} \
    [get_bd_intf_pins jacobi_evd_0/s_axi_control]
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

# Streams: MM2S -> scm_unitary -> jacobi_evd -> S2MM
connect_bd_intf_net [get_bd_intf_pins axi_dma_0/M_AXIS_MM2S] [get_bd_intf_pins scm_unitary_0/x_in]
connect_bd_intf_net [get_bd_intf_pins scm_unitary_0/r_out] [get_bd_intf_pins jacobi_evd_0/r_in]
connect_bd_intf_net [get_bd_intf_pins jacobi_evd_0/e_out] [get_bd_intf_pins axi_dma_0/S_AXIS_S2MM]

# Clock and reset of the kernel (normally done by the AXI-Lite automation)
set rst [lindex [get_bd_cells -filter {VLNV =~ *proc_sys_reset*}] 0]
foreach k {scm_unitary_0 jacobi_evd_0} {
    if {[llength [get_bd_nets -quiet -of_objects [get_bd_pins $k/ap_clk]]] == 0} {
        connect_bd_net [get_bd_pins processing_system7_0/FCLK_CLK0] [get_bd_pins $k/ap_clk]
    }
    if {[llength [get_bd_nets -quiet -of_objects [get_bd_pins $k/ap_rst_n]]] == 0} {
        connect_bd_net [get_bd_pins $rst/peripheral_aresetn] [get_bd_pins $k/ap_rst_n]
    }
}

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
