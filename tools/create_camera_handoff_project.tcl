# Portable project creation for the physically preferred camera baseline.
# argv: SOURCE_CAMERA_DIRECTORY NEW_PROJECT_DIRECTORY
# Does not synthesize, open hardware, program the FPGA, or write board flash.
if {[llength $argv] != 2} {error {Supply source camera directory and a NEW project directory}}
set src [file normalize [lindex $argv 0]]
set dest [file normalize [lindex $argv 1]]
if {![file isdirectory [file join $src rtl]] || ![file exists [file join $src constraints genesys2.xdc]]} {
    error {Source camera directory must contain rtl/ and constraints/genesys2.xdc}
}
if {[file exists $dest]} {error {Project directory already exists; choose a new directory}}
create_project camera_hdmi $dest -part xc7k325tffg900-2
add_files -norecurse [glob [file join $src rtl *.v]]
add_files -fileset constrs_1 -norecurse [file join $src constraints genesys2.xdc]
set_property top top_genesys2 [current_fileset]
set_property generic SIM_FAST_INIT=0 [current_fileset]
set_property -name {STEPS.SYNTH_DESIGN.ARGS.MORE OPTIONS} -value {-max_bram_cascade_height 1} -objects [get_runs synth_1]
set_param general.maxThreads 1
update_compile_order -fileset sources_1
puts "HANDOFF_PROJECT_READY: $dest/camera_hdmi.xpr"
puts {No synthesis, implementation or hardware programming was performed.}
