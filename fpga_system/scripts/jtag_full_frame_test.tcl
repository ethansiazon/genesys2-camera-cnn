# Full-frame real-hardware test: load an entire 256x192 packed photo (not
# just one row), trigger cnn_engine for real, and dump the complete HEAD0 +
# HEAD1 output region to a file for offline (Python) decoding. Builds on
# scripts/jtag_photo_test.tcl's row-147 test and its two real findings:
# the ap_done read-to-clear fix, and that cnn_engine/CDC genuinely works on
# real hardware (~60ms real passes, data-dependent output).
#
# Usage: vivado -mode batch -source scripts/jtag_full_frame_test.tcl \
#            -tclargs <bitstream.bit> <feature_full_lanes32.hex> <out_dump.hex>

if {[llength $argv] < 3} {
    puts "Usage: jtag_full_frame_test.tcl <bitstream.bit> <feature_full_lanes32.hex> <out_dump.hex>"
    exit 1
}
set bitstream [lindex $argv 0]
set lanes_file [lindex $argv 1]
set dump_file [lindex $argv 2]
set probes_file [file rootname $bitstream].ltx
if {![file exists $probes_file]} {
    puts "ERROR: no .ltx at $probes_file -- run scripts/program.tcl first."
    exit 1
}

set FEATURE_BASE_ADDR       0x80000000
set COEFFICIENT_BASE_ADDR   0x80300000
set ADDR_AP_CTRL            0x00
set ADDR_FEATURES_DATA_0    0x10
set ADDR_FEATURES_DATA_1    0x14
set ADDR_COEFFICIENTS_DATA_0 0x1c
set ADDR_COEFFICIENTS_DATA_1 0x20
# From cnn_hls_work/program.h (256-bit/32-byte words):
set HEAD0_OFFSET_WORDS 18432
set HEAD0_WORDS        9216
set HEAD1_OFFSET_WORDS 0
set HEAD1_WORDS        2304

open_hw_manager
connect_hw_server
open_hw_target
set dev [lindex [get_hw_devices] 0]
puts "Target device: $dev"
set_property PROGRAM.FILE $bitstream $dev
set_property PROBES.FILE $probes_file $dev
program_hw_devices $dev

set axi_core ""
for {set attempt 1} {$attempt <= 5} {incr attempt} {
    after 2000
    refresh_hw_device -update_hw_probes true $dev
    set axi_core [lindex [get_hw_axis -of_objects $dev -quiet] 0]
    if {$axi_core ne ""} break
    puts "Debug hub/hw_axi not found yet (attempt $attempt/5), retrying..."
}
if {$axi_core eq ""} { puts "ERROR: no hw_axi core found."; exit 1 }
puts "AXI debug core: $axi_core"

proc axi_write1 {core addr data} {
    create_hw_axi_txn -force t_w $core -address $addr -data [format %08x $data] -len 1 -type write
    run_hw_axi [get_hw_axi_txns t_w]
}
proc axi_read1 {core addr} {
    create_hw_axi_txn -force t_r $core -address $addr -len 1 -type read
    run_hw_axi [get_hw_axi_txns t_r]
    set result [get_property DATA [get_hw_axi_txns t_r]]
    set clean [string trim [lindex [split $result "_"] 0]]
    if {![scan $clean %x value]} { set value 0 }
    return $value
}
proc axi_write_burst {core base_addr words} {
    set n [llength $words]
    set i 0
    set bursts 0
    while {$i < $n} {
        set chunk_len [expr {min(256, $n - $i)}]
        set chunk [lrange $words $i [expr {$i + $chunk_len - 1}]]
        set data_str [join $chunk "_"]
        set addr [format "0x%016x" [expr {$base_addr + 4 * $i}]]
        create_hw_axi_txn -force t_wb $core -address $addr -data $data_str -len $chunk_len -type write
        run_hw_axi [get_hw_axi_txns t_wb]
        incr i $chunk_len
        incr bursts
    }
    puts "wrote $n words (32-bit) in $bursts bursts, starting at [format 0x%016x $base_addr]"
}
# Burst read: returns a flat Tcl list of 32-bit unsigned ints, ascending
# address order. DATA for a len>1 read comes back as ONE concatenated hex
# string (8 hex chars per beat, NO separator -- unlike the underscore-
# joined format -data expects for writes), with beats in REVERSE order
# (last beat first). Verified directly: a 4-beat read at known register
# addresses (0x10/0x14/0x18/0x1c) returned
# "80300000000000000000000080000000" -- chunking by 8 and reversing gives
# [80000000, 00000000, 00000000, 80300000], matching the known register
# contents exactly. Found by actually probing it, not by inspection/guess.
proc axi_read_burst {core base_addr count} {
    set out {}
    set i 0
    set bursts 0
    while {$i < $count} {
        set chunk_len [expr {min(256, $count - $i)}]
        set addr [format "0x%016x" [expr {$base_addr + 4 * $i}]]
        create_hw_axi_txn -force t_rb $core -address $addr -len $chunk_len -type read
        run_hw_axi [get_hw_axi_txns t_rb]
        set result [string trim [get_property DATA [get_hw_axi_txns t_rb]]]
        set n_beats [expr {[string length $result] / 8}]
        set beats {}
        for {set b 0} {$b < $n_beats} {incr b} {
            set hexchunk [string range $result [expr {$b*8}] [expr {$b*8+7}]]
            if {![scan $hexchunk %x v]} { set v 0 }
            lappend beats $v
        }
        # beats is in reverse (last-beat-first) order -- reverse it back
        # to ascending address order before appending.
        for {set b [expr {[llength $beats]-1}]} {$b >= 0} {incr b -1} {
            lappend out [lindex $beats $b]
        }
        incr i $chunk_len
        incr bursts
    }
    puts "read $count words (32-bit) in $bursts bursts, starting at [format 0x%016x $base_addr]"
    return $out
}

puts "Waiting 5s for automatic boot sequence..."
after 5000

set fh [open $lanes_file r]
set lane_words [split [string trim [read $fh]] "\n"]
close $fh
puts "Loaded [llength $lane_words] feature lanes from $lanes_file"
set t_load_start [clock milliseconds]
axi_write_burst $axi_core $FEATURE_BASE_ADDR $lane_words
set t_load_end [clock milliseconds]
puts "Full-frame load took [expr {$t_load_end - $t_load_start}]ms."

set stale [axi_read1 $axi_core $ADDR_AP_CTRL]
puts [format "Cleared stale AP_CTRL = 0x%08x" $stale]

axi_write1 $axi_core $ADDR_FEATURES_DATA_0 $FEATURE_BASE_ADDR
axi_write1 $axi_core $ADDR_FEATURES_DATA_1 0
axi_write1 $axi_core $ADDR_COEFFICIENTS_DATA_0 $COEFFICIENT_BASE_ADDR
axi_write1 $axi_core $ADDR_COEFFICIENTS_DATA_1 0
set t0 [clock milliseconds]
axi_write1 $axi_core $ADDR_AP_CTRL 0x00000001
set polls 0
set max_polls 2000
set done 0
while {$polls < $max_polls} {
    set ctrl [axi_read1 $axi_core $ADDR_AP_CTRL]
    if {[expr {($ctrl>>1) & 1}] != 0} { set done 1; break }
    incr polls
}
set t_end [clock milliseconds]
if {!$done} {
    puts "TIMEOUT: ap_done not observed after $max_polls polls."
    exit 1
}
puts "ap_done after $polls polls, [expr {$t_end-$t0}]ms wall clock (full real frame)."

# Dump HEAD1 then HEAD0 (in that offset order) to the output file: one
# 32-bit hex lane per line, HEAD1's words first then HEAD0's, each word's
# 8 lanes in ascending order -- Python-side decoder reads this back as a
# flat array and reshapes using HEAD{0,1}_WORDS from program.h.
set head1_lanes [axi_read_burst $axi_core [expr {$FEATURE_BASE_ADDR + 32*$HEAD1_OFFSET_WORDS}] [expr {$HEAD1_WORDS*8}]]
set head0_lanes [axi_read_burst $axi_core [expr {$FEATURE_BASE_ADDR + 32*$HEAD0_OFFSET_WORDS}] [expr {$HEAD0_WORDS*8}]]
set out [open $dump_file w]
puts $out "# HEAD1_WORDS=$HEAD1_WORDS"
foreach v $head1_lanes { puts $out [format %08x $v] }
puts $out "# HEAD0_WORDS=$HEAD0_WORDS"
foreach v $head0_lanes { puts $out [format %08x $v] }
close $out
puts "Dumped HEAD1 ($HEAD1_WORDS words) + HEAD0 ($HEAD0_WORDS words) to $dump_file"
close_hw_target
