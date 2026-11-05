# Real-hardware test of decode_work_heads_0: trigger cnn_engine on a real
# photo (same as scripts/jtag_full_frame_test.tcl), then trigger the
# decoder against cnn_engine's output, and read back its result.
#
# decode_work_heads_0's control register addresses are OFFSET BY 0x1000
# from jtag_axi_0's perspective (confirmed from this build's own
# assign_bd_address output: "jtag_axi_0/Data/SEG_decode_work_heads_0_reg0
# OFFSET=0x00001000") -- NOT the same as the relative offsets documented in
# decode_work_heads_control_s_axi.v itself, which are local to the
# decoder's own register file.
#
# BEST_O field layout is a BEST GUESS (DATA_0-3=x,y,w,h; DATA_4=confidence;
# DATA_5=raw_objectness; DATA_6=index+valid), not traced from the generated
# netlist (impractical by inspection -- HLS's RTL backend assembles it
# through synthesized shift/OR logic, not a clean bit-range assignment).
# Confirm/correct by matching the real readback against
# scripts/decode_heads.py's already-validated Python port of the exact
# same reference algorithm on the exact same real photo data.
#
# Usage: vivado -mode batch -source scripts/jtag_decode_test.tcl \
#            -tclargs <bitstream.bit> <feature_full_lanes32.hex>

if {[llength $argv] < 2} {
    puts "Usage: jtag_decode_test.tcl <bitstream.bit> <feature_full_lanes32.hex>"
    exit 1
}
set bitstream [lindex $argv 0]
set lanes_file [lindex $argv 1]
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

# decode_work_heads_0's own control block, offset +0x1000 from jtag_axi_0's
# base (confirmed from this build's assign_bd_address output).
#
# ROOT CAUSE FOUND (2026-10-29): every DEC_* address below was computed via
# plain `[expr {$DEC_BASE + ...}]`, which Tcl stringifies in DECIMAL (e.g.
# 0x1000+0x00 -> the string "4096", not "0x1000") -- confirmed directly:
# `puts [expr {0x1000+0x00}]` prints "4096". create_hw_axi_txn's -address
# apparently treats a bare numeric string as hex regardless of this
# decimal formatting, so "4096" was silently read as address 0x4096 --
# completely unmapped, outside decode_work_heads_0's actual 0x1000-0x1fff
# control window -- landing on a fixed bus "no response" sentinel
# (0xdec0dee3) every single time. 100% reproducible, not flaky: every
# plain cnn_engine address (hardcoded hex literals like 0x00, 0x10) always
# worked; every computed DEC_* address always failed, identically. `format
# "0x%x"` forces the real hex string Vivado's tooling actually expects.
set DEC_BASE                0x1000
set DEC_AP_CTRL             [format "0x%x" [expr {$DEC_BASE + 0x00}]]
set DEC_FEATURES_DATA_0     [format "0x%x" [expr {$DEC_BASE + 0x10}]]
set DEC_FEATURES_DATA_1     [format "0x%x" [expr {$DEC_BASE + 0x14}]]
set DEC_CFG_DATA_0          [format "0x%x" [expr {$DEC_BASE + 0x1c}]]  ;# sx
set DEC_CFG_DATA_1          [format "0x%x" [expr {$DEC_BASE + 0x20}]]  ;# sy
set DEC_CFG_DATA_2          [format "0x%x" [expr {$DEC_BASE + 0x24}]]  ;# ox
set DEC_CFG_DATA_3          [format "0x%x" [expr {$DEC_BASE + 0x28}]]  ;# oy
set DEC_CFG_DATA_4          [format "0x%x" [expr {$DEC_BASE + 0x2c}]]  ;# u
set DEC_CFG_DATA_5          [format "0x%x" [expr {$DEC_BASE + 0x30}]]  ;# v
set DEC_CFG_DATA_6          [format "0x%x" [expr {$DEC_BASE + 0x34}]]  ;# mx
set DEC_CFG_DATA_7          [format "0x%x" [expr {$DEC_BASE + 0x38}]]  ;# my
set DEC_CFG_DATA_8          [format "0x%x" [expr {$DEC_BASE + 0x3c}]]  ;# use_motion
set DEC_CFG_DATA_9          [format "0x%x" [expr {$DEC_BASE + 0x40}]]  ;# rx
set DEC_CFG_DATA_10         [format "0x%x" [expr {$DEC_BASE + 0x44}]]  ;# ry
set DEC_CFG_DATA_11         [format "0x%x" [expr {$DEC_BASE + 0x48}]]  ;# rw
set DEC_CFG_DATA_12         [format "0x%x" [expr {$DEC_BASE + 0x4c}]]  ;# rh
set DEC_CFG_DATA_13         [format "0x%x" [expr {$DEC_BASE + 0x50}]]  ;# use_association
set DEC_BEST_O_DATA_0       [format "0x%x" [expr {$DEC_BASE + 0x78}]]
set DEC_BEST_O_DATA_1       [format "0x%x" [expr {$DEC_BASE + 0x7c}]]
set DEC_BEST_O_DATA_2       [format "0x%x" [expr {$DEC_BASE + 0x80}]]
set DEC_BEST_O_DATA_3       [format "0x%x" [expr {$DEC_BASE + 0x84}]]
set DEC_BEST_O_DATA_4       [format "0x%x" [expr {$DEC_BASE + 0x88}]]
set DEC_BEST_O_DATA_5       [format "0x%x" [expr {$DEC_BASE + 0x8c}]]
set DEC_BEST_O_DATA_6       [format "0x%x" [expr {$DEC_BASE + 0x90}]]

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

puts "Waiting 5s for automatic boot sequence..."
after 5000

set fh [open $lanes_file r]
set lane_words [split [string trim [read $fh]] "\n"]
close $fh
puts "Loaded [llength $lane_words] feature lanes from $lanes_file"
axi_write_burst $axi_core $FEATURE_BASE_ADDR $lane_words

# Sanity check + settle after the large (1536-burst) write: read back a
# known register and confirm it's not the debug-bridge "stuck" garbage
# pattern seen once already (every register reading back an identical
# 0xdec0dee3 after a big burst sequence -- looked like the same class of
# transient debug-hub instability seen earlier this session around
# refresh_hw_device timing, not a real design bug: an isolated diagnostic
# immediately after read clean values from the exact same registers).
after 500
set sanity [axi_read1 $axi_core $ADDR_FEATURES_DATA_0]
if {$sanity == 0xdec0dee3 || ($sanity != $FEATURE_BASE_ADDR && $sanity != 0)} {
    puts [format "WARNING: post-burst sanity read looks wrong (0x%08x) -- debug bridge may be stuck. Retrying refresh_hw_device." $sanity]
    refresh_hw_device -update_hw_probes true $dev
    after 1000
    set sanity [axi_read1 $axi_core $ADDR_FEATURES_DATA_0]
    puts [format "  after refresh: 0x%08x" $sanity]
}

# --- Stage 1: trigger cnn_engine (clear stale ap_done first, see
# docs/PHASE2_LOG.md's read-to-clear correction) ---
set stale [axi_read1 $axi_core $ADDR_AP_CTRL]
puts [format "Cleared stale cnn_engine AP_CTRL = 0x%08x" $stale]
axi_write1 $axi_core $ADDR_FEATURES_DATA_0 $FEATURE_BASE_ADDR
axi_write1 $axi_core $ADDR_FEATURES_DATA_1 0
axi_write1 $axi_core $ADDR_COEFFICIENTS_DATA_0 $COEFFICIENT_BASE_ADDR
axi_write1 $axi_core $ADDR_COEFFICIENTS_DATA_1 0
set t0 [clock milliseconds]
axi_write1 $axi_core $ADDR_AP_CTRL 0x00000001
set polls 0
set done 0
while {$polls < 2000} {
    set ctrl [axi_read1 $axi_core $ADDR_AP_CTRL]
    if {[expr {($ctrl>>1) & 1}] != 0} { set done 1; break }
    incr polls
}
if {!$done} { puts "TIMEOUT waiting for cnn_engine ap_done"; exit 1 }
puts "cnn_engine ap_done after $polls polls, [expr {[clock milliseconds]-$t0}]ms."

# Settle: the decoder's control-register reads came back as a fixed
# "0xdec0dee3" sentinel (debug bridge's own stuck/no-response placeholder,
# not a design value -- not found anywhere in this project's RTL or
# scripts) immediately after cnn_engine's ap_done, every time, while an
# isolated cold-boot diagnostic read the exact same registers cleanly.
# Hypothesis: cnn_engine's heavy DDR traffic on the shared smartconnect
# crossbar, still trailing right at the ap_done edge, starves the
# low-priority JTAG debug read until the bridge times out. Settle before
# touching decode's registers at all.
after 1000

# --- Stage 2: configure + trigger decode_work_heads_0 (identity/no-motion
# config -- DECODER_PREPARED.json's "actualV5zero" query) ---
set stale2 [axi_read1 $axi_core $DEC_AP_CTRL]
puts [format "Cleared stale decoder AP_CTRL = 0x%08x" $stale2]
axi_write1 $axi_core $DEC_FEATURES_DATA_0 $FEATURE_BASE_ADDR
axi_write1 $axi_core $DEC_FEATURES_DATA_1 0
axi_write1 $axi_core $DEC_CFG_DATA_0  65536  ;# sx = Q16 1.0
axi_write1 $axi_core $DEC_CFG_DATA_1  65536  ;# sy = Q16 1.0
axi_write1 $axi_core $DEC_CFG_DATA_2  0      ;# ox
axi_write1 $axi_core $DEC_CFG_DATA_3  0      ;# oy
axi_write1 $axi_core $DEC_CFG_DATA_4  0      ;# u
axi_write1 $axi_core $DEC_CFG_DATA_5  0      ;# v
axi_write1 $axi_core $DEC_CFG_DATA_6  524288 ;# mx
axi_write1 $axi_core $DEC_CFG_DATA_7  524288 ;# my
axi_write1 $axi_core $DEC_CFG_DATA_8  0      ;# use_motion
axi_write1 $axi_core $DEC_CFG_DATA_9  0      ;# rx
axi_write1 $axi_core $DEC_CFG_DATA_10 0      ;# ry
axi_write1 $axi_core $DEC_CFG_DATA_11 0      ;# rw
axi_write1 $axi_core $DEC_CFG_DATA_12 0      ;# rh
axi_write1 $axi_core $DEC_CFG_DATA_13 0      ;# use_association

set t1 [clock milliseconds]
axi_write1 $axi_core $DEC_AP_CTRL 0x00000001
set polls2 0
set done2 0
while {$polls2 < 2000} {
    set ctrl2 [axi_read1 $axi_core $DEC_AP_CTRL]
    if {[expr {($ctrl2>>1) & 1}] != 0} { set done2 1; break }
    incr polls2
}
if {!$done2} { puts "TIMEOUT waiting for decode_work_heads_0 ap_done"; exit 1 }
puts "decoder ap_done after $polls2 polls, [expr {[clock milliseconds]-$t1}]ms."

puts "--- BEST_O raw registers ---"
foreach {name addr} [list DATA_0 $DEC_BEST_O_DATA_0 DATA_1 $DEC_BEST_O_DATA_1 \
        DATA_2 $DEC_BEST_O_DATA_2 DATA_3 $DEC_BEST_O_DATA_3 \
        DATA_4 $DEC_BEST_O_DATA_4 DATA_5 $DEC_BEST_O_DATA_5 \
        DATA_6 $DEC_BEST_O_DATA_6] {
    set v [axi_read1 $axi_core $addr]
    set signed_v $v
    if {$v > 0x7fffffff} { set signed_v [expr {$v - 0x100000000}] }
    puts [format "  %s (0x%04x): raw=0x%08x  signed=%d  as_Q16=%0.2f" $name $addr $v $signed_v [expr {$signed_v / 65536.0}]]
}
close_hw_target
