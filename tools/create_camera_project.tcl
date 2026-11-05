# Create only: source is camera/working; generated project is external/new.
set root [file dirname [file dirname [file normalize [info script]]]]
if {[llength $argv] != 1} {error {Usage: set argv [list NEW_PROJECT_DIR]; source tools/create_camera_project.tcl}}
set dest [file normalize [lindex $argv 0]]
if {[file exists $dest]} {error {Existing directory refused; select a new project output path}}
set src [file join $root camera working]
create_project camera_hdmi $dest -part xc7k325tffg900-2
add_files -norecurse [glob [file join $src rtl *.v]]
add_files -fileset constrs_1 -norecurse [file join $src constraints genesys2.xdc]
set_property top top_genesys2 [current_fileset]
set_property generic SIM_FAST_INIT=0 [current_fileset]
set_property -name {STEPS.SYNTH_DESIGN.ARGS.MORE OPTIONS} -value {-max_bram_cascade_height 1} -objects [get_runs synth_1]
set_param general.maxThreads 2
update_compile_order -fileset sources_1
puts {Working camera project created. No build or board programming started.}
