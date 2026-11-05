set root [file dirname [file dirname [file normalize [info script]]]]
set proj [file join $root vivado]
if {[file exists [file join $proj camera_hdmi.xpr]]} {
    open_project [file join $proj camera_hdmi.xpr]
} else {
    create_project camera_hdmi $proj -part xc7k325tffg900-2
    add_files -norecurse [glob [file join $root rtl *.v]]
    add_files -fileset constrs_1 -norecurse [file join $root constraints genesys2.xdc]
    set_property top top_genesys2 [get_filesets sources_1]
    set_property generic SIM_FAST_INIT=0 [get_filesets sources_1]
    set_param general.maxThreads 2
    update_compile_order -fileset sources_1
}
puts "CAMERA PROJECT: $proj/camera_hdmi.xpr"
