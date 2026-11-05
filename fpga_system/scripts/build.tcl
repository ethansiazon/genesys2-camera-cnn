# Synthesise and implement the standalone CNN+DDR3/AXI timing subsystem.
# Fails loudly. Modeled on the vivado-build-and-flash skill's template.
#
# Run scripts/create_project.tcl + bd/create_bd.tcl FIRST, WITHOUT
# PHASE2_SIM_BYPASS_CAL set in the environment -- that env var gates
# SIM_BYPASS_INIT_CAL=FAST and a 256-word coefficient-count reduction that
# are simulation-only (Task 4). This build must run at the real hardware
# configuration: full calibration, full 41,600-word coefficient set.
set proj_name genesys2_cv
set top_mod   cnn_subsystem_top

set here [file dirname [file normalize [info script]]]
set root [file dirname $here]
open_project [file join $root vivado $proj_name.xpr]

if {[info exists ::env(PHASE2_SIM_BYPASS_CAL)]} {
    puts "BUILD FAILED: PHASE2_SIM_BYPASS_CAL is set in the environment -- this is the simulation-only override (Task 4) and must NOT leak into the hardware build. Unset it and rebuild the project from scratch."
    exit 1
}
# Must open the block design before querying its cells -- get_bd_cells on
# a project with no open BD returns an empty object, and get_property on
# that hard-errors ("Invalid option value '' specified for 'object'")
# rather than just failing the eq check below.
open_bd_design [get_files cv_subsystem.bd]
set bypass_prop [get_property CONFIG.SIM_BYPASS_INIT_CAL [get_bd_cells -quiet /mig_7series_0]]
if {$bypass_prop eq "FAST"} {
    puts "BUILD FAILED: mig_7series_0/CONFIG.SIM_BYPASS_INIT_CAL is FAST, not the hardware default. The project was built with PHASE2_SIM_BYPASS_CAL set. Rebuild from scratch without it."
    exit 1
}

# 125MHz timing closure (2026-10-29): same more-aggressive strategies that
# were needed to close timing at this frequency in the isolated-copy
# experiment -- see docs/PHASE2_LOG.md's 125MHz section. cnn_engine_0 itself
# was never the limiter in the 200/150/135/125MHz experiments; the
# repeatedly-tight path is inside decode_work_heads_0's own arithmetic
# (width_q/transformed multipliers).
set_property strategy Flow_PerfOptimized_high [get_runs synth_1]
set_property strategy Performance_Retiming [get_runs impl_1]
set_property STEPS.PHYS_OPT_DESIGN.IS_ENABLED true [get_runs impl_1]

reset_run synth_1
launch_runs synth_1 -jobs 8
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {
    puts "BUILD FAILED: synthesis"
    exit 1
}

# CRITICAL FIX (code review, 2026-10-28): Task 5's original build.tcl only
# grepped the TOP-LEVEL build.log for CRITICAL, per the plan's own Step 3 --
# but the warning that silently dissolved coeff_bram_stage's entire 41,600-
# word BRAM array into nothing ([Synth 8-4445], "could not open $readmem
# data file") landed in that IP's own per-run
# vivado/*.runs/*/runme.log, which build.log never captures. Sweep every
# per-IP runme.log explicitly and fail on any CRITICAL WARNING not on the
# allowlist below. A build that silently drops part of the design must not
# be able to print BUILD OK.
set allowlisted_critical_patterns {
    {RUSER_WIDTH .* of .*AXI must be integer number of bits per byte}
    {WUSER_WIDTH .* of .*AXI must be integer number of bits per byte}
}
set unexpected_criticals {}
foreach log_file [glob -nocomplain [file join $root vivado *.runs *]/runme.log] {
    set fh [open $log_file r]
    set content [read $fh]
    close $fh
    foreach line [split $content "\n"] {
        if {[string match "*CRITICAL WARNING*" $line]} {
            set allowed 0
            foreach pat $allowlisted_critical_patterns {
                if {[regexp $pat $line]} { set allowed 1; break }
            }
            if {!$allowed} {
                lappend unexpected_criticals "$log_file: $line"
            }
        }
    }
}
if {[llength $unexpected_criticals] > 0} {
    puts "BUILD FAILED: unexpected CRITICAL WARNING(s) in per-IP synthesis logs:"
    foreach c $unexpected_criticals { puts "  $c" }
    exit 1
}
puts "No unexpected CRITICAL WARNINGs in any per-IP runme.log ([llength [glob -nocomplain [file join $root vivado *.runs *]/runme.log]] logs checked)"

# BUG FOUND (2026-10-29, first real-hardware prep): this previously read
# plain `launch_runs impl_1 -jobs 8`, which only runs through route_design
# -- every prior "BUILD OK" in this project's history meant "timing/BRAM
# checks passed", NOT "a flashable .bit exists" (there was no bitstream at
# all, found when scripts/program.tcl went looking for one). -to_step
# write_bitstream makes BUILD OK actually mean a bitstream was produced.
launch_runs impl_1 -jobs 8 -to_step write_bitstream
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {
    puts "BUILD FAILED: implementation"
    exit 1
}

open_run impl_1
set wns [get_property SLACK [get_timing_paths -delay_type max]]
puts "=== RESULTS ==="
puts "WNS: $wns ns"
if {$wns < 0} {
    puts "TIMING NOT MET"
} else {
    puts "TIMING MET"
}
report_utilization -hierarchical -file [file join $root vivado utilization.rpt]
report_timing_summary -file [file join $root vivado timing_summary.rpt]

# Sanity-check coeff_bram_stage_0 actually has real BRAM content this time
# (the exact check that would have caught C1 immediately) -- read the
# hierarchical utilization report back and confirm its RAMB36 count is
# nonzero.
set util_fh [open [file join $root vivado utilization.rpt] r]
set util_content [read $util_fh]
close $util_fh
set coeff_line ""
foreach line [split $util_content "\n"] {
    if {[string match "*coeff_bram_stage_0*" $line] && [string match "*cv_subsystem_coeff_bram_stage_0_0*" $line]} {
        set coeff_line $line
        break
    }
}
if {$coeff_line eq ""} {
    puts "BUILD FAILED: could not find coeff_bram_stage_0's row in utilization.rpt at all"
    exit 1
}
puts "coeff_bram_stage_0 utilization row: $coeff_line"
# Columns (pipe-delimited): ... | Total LUTs | Logic LUTs | LUTRAMs | SRLs |
# FFs | RAMB36 | RAMB18 | DSP Blocks |. Parse from the right rather than
# regex-matching the whole row shape, which is fragile to column changes.
set raw_fields [split $coeff_line "|"]
# lmap is Tcl 8.6+; Vivado 2023.2's Tcl interpreter does not have it
# ("invalid command name lmap" -- found by actually running this, not by
# inspection). foreach + lappend works on any Tcl version.
set fields {}
foreach f $raw_fields { lappend fields [string trim $f] }
set fields [lsearch -all -inline -not -exact $fields ""]
set n [llength $fields]
set ramb36 [lindex $fields [expr {$n - 3}]]
set ramb18 [lindex $fields [expr {$n - 2}]]
if {$ramb36 == 0 && $ramb18 == 0} {
    puts "BUILD FAILED: coeff_bram_stage_0 shows 0 RAMB36 and 0 RAMB18 -- the coefficient array was dissolved away, same as the original C1 bug. Check for Synth 8-4445 in its runme.log."
    exit 1
}

set bit_path [file join $root vivado genesys2_cv.runs impl_1 cnn_subsystem_top.bit]
if {![file exists $bit_path]} {
    puts "BUILD FAILED: no bitstream at $bit_path despite implementation reporting 100% progress."
    exit 1
}
puts "BITSTREAM: $bit_path"

puts "BUILD OK"
