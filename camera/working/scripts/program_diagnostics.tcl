# One controlled programming attempt following FTDI repair and laptop restart.
# Default JTAG connection; UART must be disconnected. No configuration flash write.
set root [file dirname [file dirname [file normalize [info script]]]]
set statefile [file join $root reports program_diagnostics_state.txt]
proc record_stage {stage} {
    global statefile
    set f [open $statefile w]
    puts $f "[clock format [clock seconds] -format {%Y-%m-%dT%H:%M:%S%z}] $stage"
    close $f
    puts "CAMERA_REPAIR_TEST_STAGE: $stage"
}
set bitfile [file join $root camera_hdmi.bit]
if {![file exists [file join $root WIRING_CONFIRMED.txt]]} {error "Current camera wiring not confirmed"}
if {![file exists $bitfile]} {error "Saved camera bitstream missing"}
record_stage STARTED
if {[catch {
    open_hw_manager
    record_stage CONNECTING_JTAG_SERVER
    connect_hw_server
    record_stage SERVER_CONNECTED
    set targets [get_hw_targets *]
    if {[llength $targets] != 1} {error "Expected one connected JTAG target; found $targets"}
    current_hw_target [lindex $targets 0]
    open_hw_target
    record_stage TARGET_OPEN
    set devices [get_hw_devices -filter {PART =~ "xc7k325t*"}]
    if {[llength $devices] != 1} {error "Expected exactly one XC7K325T; found [get_hw_devices]"}
    set dev [lindex $devices 0]
    current_hw_device $dev
    refresh_hw_device -update_hw_probes false $dev
    set_property PROGRAM.FILE $bitfile $dev
    record_stage PROGRAMMING_SAVED_CAMERA_BUILD
    program_hw_devices $dev
    refresh_hw_device -update_hw_probes false $dev
    set f [open [file join $root reports program_result.txt] w]
    puts $f "device=$dev"
    puts $f "part=[get_property PART $dev]"
    puts $f "bitstream=$bitfile"
    puts $f "configuration_status=[get_property REGISTER.CONFIG_STATUS $dev]"
    puts $f "method=JTAG only; camera diagnostics"
    close $f
    record_stage PROGRAM_COMPLETE
    close_hw_target
    disconnect_hw_server
    close_hw_manager
} message options]} {
    record_stage "FAILED: $message"
    catch {close_hw_manager}
    return -options $options $message
}
puts CAMERA_JTAG_PROGRAM_COMPLETE

