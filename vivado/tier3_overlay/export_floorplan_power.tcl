# =====================================================================
# export_floorplan_power.tcl -- floorplan data and power estimate of the routed Tier 3 overlay
#
# Prerequisite: build_tier3_overlay.tcl has been run, so build/tier3_overlay.xpr holds a routed
# implementation (impl_1).
#
# Usage (from this folder):
#     vivado -mode batch -source export_floorplan_power.tcl
#
# Outputs (in output/):
#     power.rpt               report_power: total, static, dynamic, and per block
#     utilization_hier.rpt    report_utilization -hierarchical: LUT/FF/DSP/BRAM per block
#     placement_used.csv      one line per used site: block, site type, RPM_X, RPM_Y, clock region
#     placement_all.csv       all SLICE/DSP/BRAM sites of the device (background of the plot)
#
# Then, on any computer with Python and matplotlib:
#     python plot_floorplan.py output
# =====================================================================

set script_dir [file dirname [file normalize [info script]]]
set proj_name  tier3_overlay
set proj_file  [file join $script_dir build $proj_name.xpr]
set out_dir    [file join $script_dir output]
file mkdir $out_dir

if {![file exists $proj_file]} {
    error "Project not found: $proj_file. Run build_tier3_overlay.tcl first."
}
open_project $proj_file
open_run impl_1

# ---------------------------------------------------------------------
# 1. Power and per-block utilization
# ---------------------------------------------------------------------
# Vectorless estimate with default toggle rates; the confidence level is printed in the report.
report_power -hierarchical_depth 3 -file [file join $out_dir power.rpt]
report_utilization -hierarchical -hierarchical_depth 2 -file [file join $out_dir utilization_hier.rpt]

# ---------------------------------------------------------------------
# 2. Placement of every used site, labelled with the block that owns it
# ---------------------------------------------------------------------
# Block = second level of the hierarchy (tier3_overlay_i/<block>/...).
proc block_of {cell} {
    set parts [split $cell /]
    if {[llength $parts] < 3} { return other }
    set b [lindex $parts 1]
    switch -glob -- $b {
        scm_unitary*      { return scm_unitary }
        jacobi_evd*       { return jacobi_evd }
        music_doa*        { return music_doa }
        axi_dma*          { return axi_dma }
        processing_system* { return ps7 }
        default           { return infrastructure }
    }
}

set prims [get_cells -hierarchical -filter {IS_PRIMITIVE && STATUS != UNPLACED}]
set sites [lsort -unique [get_sites -of_objects $prims]]
puts "INFO: [llength $prims] placed primitives on [llength $sites] sites"

set f [open [file join $out_dir placement_used.csv] w]
puts $f "block,site_type,rpm_x,rpm_y,clock_region"
foreach s $sites {
    # majority block of the cells on this site
    array unset cnt
    foreach c [get_cells -quiet -of_objects $s] {
        set b [block_of $c]
        if {[info exists cnt($b)]} { incr cnt($b) } else { set cnt($b) 1 }
    }
    set best other; set n 0
    foreach {b k} [array get cnt] { if {$k > $n} { set best $b; set n $k } }
    puts $f "$best,[get_property SITE_TYPE $s],[get_property RPM_X $s],[get_property RPM_Y $s],[get_property CLOCK_REGION $s]"
}
close $f

# ---------------------------------------------------------------------
# 3. All logic, DSP and BRAM sites (background of the floorplan)
# ---------------------------------------------------------------------
set f [open [file join $out_dir placement_all.csv] w]
puts $f "site_type,rpm_x,rpm_y,clock_region"
foreach s [get_sites -filter {SITE_TYPE =~ SLICE* || SITE_TYPE == DSP48E1 || SITE_TYPE == RAMB36E1}] {
    puts $f "[get_property SITE_TYPE $s],[get_property RPM_X $s],[get_property RPM_Y $s],[get_property CLOCK_REGION $s]"
}
close $f

puts "================================================================"
puts " DONE. Files in $out_dir:"
puts "   power.rpt  utilization_hier.rpt  placement_used.csv  placement_all.csv"
puts "================================================================"
