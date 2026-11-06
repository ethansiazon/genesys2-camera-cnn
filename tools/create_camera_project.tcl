# Create only: source is camera/working; generated project is external/new.
set root [file dirname [file dirname [file normalize [info script]]]]
if {[llength $argv] < 1 || [llength $argv] > 3} {error {Usage: set argv [list NEW_PROJECT_DIR ?yuyv|rgb565? ?baseline|reference2x|reference2x-fast|reference2x-20fps|reference2x-20fps-even|reference2x-20fps-filter?]; source tools/create_camera_project.tcl}}
set dest [file normalize [lindex $argv 0]]
set format yuyv
if {[llength $argv] >= 2} {set format [lindex $argv 1]}
if {$format ni {yuyv rgb565}} {error {Format must be yuyv or rgb565}}
set rgb565 [expr {$format eq "rgb565" ? 1 : 0}]
set readout baseline
if {[llength $argv] == 3} {set readout [lindex $argv 2]}
if {$readout ni {baseline reference2x reference2x-fast reference2x-20fps reference2x-20fps-even reference2x-20fps-filter}} {error {Invalid readout profile}}
set reference_readout [lsearch -exact {baseline reference2x reference2x-fast reference2x-20fps reference2x-20fps-even reference2x-20fps-filter} $readout]
if {[file exists $dest]} {error {Existing directory refused; select a new project output path}}
set src [file join $root camera working]
create_project camera_hdmi $dest -part xc7k325tffg900-2
add_files -norecurse [glob [file join $src rtl *.v]]
add_files -fileset constrs_1 -norecurse [file join $src constraints genesys2.xdc]
set_property top top_genesys2 [current_fileset]
set_property generic "SIM_FAST_INIT=0 RGB565=$rgb565 REFERENCE_READOUT=$reference_readout" [current_fileset]
set_property -name {STEPS.SYNTH_DESIGN.ARGS.MORE OPTIONS} -value {-max_bram_cascade_height 1} -objects [get_runs synth_1]
set_param general.maxThreads 2
update_compile_order -fileset sources_1
puts {Working camera project created. No build or board programming started.}
