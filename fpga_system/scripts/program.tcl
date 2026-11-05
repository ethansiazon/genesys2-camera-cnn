# Flash cnn_subsystem_top's bitstream to the Genesys 2 over JTAG.
# Volatile, same as the Basys 3 flow (vivado-build-and-flash skill): lives
# in the FPGA until power-cycle or PROG, nothing written to QSPI. Safe to
# rerun freely. NOT YET RUN AGAINST REAL HARDWARE -- no board/cable attached
# in the environment this was written in; verify the device enumerates as
# expected (xc7k325t_0) before assuming a failure here is the design's
# fault and not a cable/power/JP1 issue.
set here  [file dirname [file normalize [info script]]]
set root  [file dirname $here]
set bit   [file join $root vivado genesys2_cv.runs impl_1 cnn_subsystem_top.bit]
set ltx   [file join $root vivado genesys2_cv.runs impl_1 cnn_subsystem_top.ltx]

if {![file exists $bit]} {
    puts "PROGRAM FAILED: no bitstream at $bit -- run scripts/build.tcl first."
    exit 1
}
# Needed for jtag_axi_0 to enumerate as a hw_axi object (without it,
# refresh_hw_device reports "No matching hw_axi were found" even though the
# debug hub and AXI debug core are both actually in the bitstream -- found
# by actually running scripts/jtag_photo_test.tcl, not by inspection).
# write_debug_probes isn't part of build.tcl's normal synth+impl flow, so
# generate it here if it's missing rather than requiring a separate manual
# step before every program.tcl run.
if {![file exists $ltx]} {
    puts "No .ltx found at $ltx -- generating it now (needed for jtag_axi_0 debug-core enumeration)."
    open_project [file join $root vivado genesys2_cv.xpr]
    open_run impl_1
    write_debug_probes -force $ltx
}

open_hw_manager
connect_hw_server
open_hw_target

set devs [get_hw_devices]
puts "Devices found:"
foreach d $devs { puts "  $d" }

set dev [lindex [lsearch -inline -all -regexp $devs {xc7k325t.*}] 0]
if {$dev eq ""} {
    puts "PROGRAM FAILED: no xc7k325t device found. Check the board is powered, JP1 is on JTAG, and the USB cable carries data (not power-only)."
    exit 1
}

set_property PROGRAM.FILE $bit $dev
set_property PROBES.FILE $ltx $dev
program_hw_devices $dev
refresh_hw_device -update_hw_probes true $dev
puts "PROGRAM OK: $bit -> $dev"
set axi_cores [get_hw_axis -of_objects $dev -quiet]
puts "hw_axi cores found: $axi_cores"
