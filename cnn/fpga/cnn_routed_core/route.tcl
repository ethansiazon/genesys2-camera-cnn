set_param general.maxThreads 1
read_verilog [glob rtl/*.v]
synth_design -top cnn_engine -part xc7k325tffg900-2 -mode out_of_context
create_clock -name core_clock -period 10 [get_ports ap_clk]
write_checkpoint -force synthesized.dcp
report_utilization -file utilization_synth.rpt
opt_design
write_checkpoint -force optimized.dcp
place_design
write_checkpoint -force placed.dcp
phys_opt_design
route_design
write_checkpoint -force routed.dcp
report_route_status -file route_status.rpt
report_timing_summary -delay_type min_max -report_unconstrained -file timing.rpt
report_utilization -hierarchical -file utilization.rpt
report_drc -file drc.rpt
check_timing -verbose -file check_timing.rpt
set setup_path [get_timing_paths -quiet -delay_type max -max_paths 1]
set hold_path [get_timing_paths -quiet -delay_type min -max_paths 1]
if {[llength $setup_path] != 1 || [llength $hold_path] != 1} {error {Missing actual constrained setup/hold paths}}
set wns [get_property SLACK $setup_path]
set whs [get_property SLACK $hold_path]
set periods [get_property PERIOD [get_clocks]]
set blackboxes [llength [get_cells -hier -quiet -filter {IS_BLACKBOX == 1}]]
set fd [open timing_values.json w]
puts $fd [format {{"setup_wns_ns": %.8f,"hold_whs_ns": %.8f,"clock_periods_ns": "%s","blackbox_count":%d}} $wns $whs $periods $blackboxes]
close $fd
exit
