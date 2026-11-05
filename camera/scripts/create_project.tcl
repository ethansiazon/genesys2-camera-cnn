# Handoff wrapper; source files untouched. Args: variant, NEW project directory.
set root [file dirname [file dirname [file normalize [info script]]]]
if {[llength $argv] != 2} {error {Usage: set argv [list best_receiver C:/g2_camera_work]; source scripts/create_project.tcl}}
set variant [lindex $argv 0]
if {$variant ni {best_receiver last_exposure_test raw_recorder}} {error {Unknown camera variant}}
set dest [file normalize [lindex $argv 1]]
if {[file exists $dest]} {error {Choose a new project directory; existing work preserved}}
set src [file join $root versions $variant]
create_project camera_hdmi $dest -part xc7k325tffg900-2
add_files -norecurse [glob [file join $src rtl *.v]]
add_files -fileset constrs_1 -norecurse [file join $src constraints genesys2.xdc]
set_property top top_genesys2 [current_fileset]
set_property generic SIM_FAST_INIT=0 [current_fileset]
set_property -name {STEPS.SYNTH_DESIGN.ARGS.MORE OPTIONS} -value {-max_bram_cascade_height 1} -objects [get_runs synth_1]
set_param general.maxThreads 2
update_compile_order -fileset sources_1
puts {Project created only; no build or board programming started.}

