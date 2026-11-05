# Temporary JTAG configuration only. Does not erase or write configuration flash.
set root [file dirname [file dirname [file normalize [info script]]]]
set bitfile [file join $root camera_hdmi.bit]
if {![file exists [file join $root WIRING_CONFIRMED.txt]]} {error "Confirm physical PCLK=JA1 and D6=JB8 before programming this variant"}
if {![file exists $bitfile]} {error "No timing-checked camera bitstream exists"}
open_hw_manager
connect_hw_server
set targets [get_hw_targets *]
if {[llength $targets] != 1} {error "Expected one connected JTAG target; found: $targets"}
current_hw_target [lindex $targets 0]
open_hw_target
set devices [get_hw_devices -filter {PART =~ "xc7k325t*"}]
if {[llength $devices] != 1} {error "Expected one XC7K325T; found: [get_hw_devices]"}
set dev [lindex $devices 0]
current_hw_device $dev
refresh_hw_device -update_hw_probes false $dev
set_property PROGRAM.FILE $bitfile $dev
program_hw_devices $dev
refresh_hw_device -update_hw_probes false $dev
set f [open [file join $root reports program_result.txt] w]
puts $f "device=$dev"
puts $f "part=[get_property PART $dev]"
puts $f "bitstream=$bitfile"
puts $f "configuration_status=[get_property REGISTER.CONFIG_STATUS $dev]"
close $f
puts "CAMERA_JTAG_PROGRAM_COMPLETE"
close_hw_manager

