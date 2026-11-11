# Non-project build: outputs stay in a short writable temporary directory.
# Never connects to/programs a board. Timing failure is a build failure.
set root [file dirname [file dirname [file normalize [info script]]]]
set out [file normalize [lindex $argv 0]]
set rgb565 0
if {[llength $argv] > 1} {set rgb565 [lindex $argv 1]}
if {$rgb565 ni {0 1}} {error {RGB565 generic must be0 or1}}
set reference_readout 0
if {[llength $argv] > 2} {set reference_readout [lindex $argv 2]}
if {$reference_readout ni {0 1 2 3 4 5 6 7}} {error {REFERENCE_READOUT generic must be in 0..7}}
file mkdir $out
cd $out
set_param general.maxThreads 2
foreach source [glob [file join $root rtl *.v]] {read_verilog $source}
read_xdc [file join $root constraints genesys2.xdc]
# Prevent Vivado's deep-BRAM cascade implementation from producing REQP-1962
# mismatched ADDR15 tie-offs. Logical memory contents/latency stay unchanged.
# AMD UG835 synth_design documents this maximum cascade-height control.
synth_design -top top_genesys2 -part xc7k325tffg900-2 -max_bram_cascade_height 1 -generic [list RGB565=$rgb565 REFERENCE_READOUT=$reference_readout]
write_checkpoint -force synthesized.dcp
opt_design
place_design
phys_opt_design
route_design
report_timing_summary -report_unconstrained -max_paths 10 -file timing.rpt
report_utilization -file utilization.rpt
report_drc -file drc.rpt
report_cdc -details -file cdc.rpt
report_clock_interaction -file clock_interaction.rpt
report_route_status -file route_status.rpt
write_checkpoint -force routed.dcp
set setup_path [get_timing_paths -delay_type max -max_paths 1]
set hold_path [get_timing_paths -delay_type min -max_paths 1]
set wns [get_property SLACK $setup_path]
set whs [get_property SLACK $hold_path]
set f [open timing_values.json w]
puts $f "{\"setup_wns_ns\":$wns,\"hold_whs_ns\":$whs,\"physical_camera_tested\":false}"
close $f
if {$wns < 0 || $whs < 0} {error "Timing not met: setup=$wns hold=$whs. No bitstream promoted."}
write_bitstream -force camera_hdmi.bit
puts "CAMERA_BUILD_PASSED: $out/camera_hdmi.bit"
