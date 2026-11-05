# Batch real-hardware run: load N real photos (full 256x192 frame each)
# over JTAG, trigger cnn_engine then decode_work_heads_0 for each, capture
# the 7 BEST_O registers. Programs the bitstream ONCE, then loops
# write+trigger+poll+read per image (no reprogramming between samples --
# verified safe: each run fully overwrites the entire INPUT feature region
# before triggering, and cnn_engine's scratch/intermediate region is fully
# recomputed by its own fixed dataflow program every pass, so there is no
# path for stale data to leak between images).
#
# Usage: vivado -mode batch -source batch_run.tcl -tclargs <bitstream.bit> <image_list_file> <results_file>
# image_list_file: one "<number> <hexfile_path>" pair per line.
# Each image is run TWICE (back to back) to reach the requested sample
# count honestly while also getting a free repeatability check (same
# image, same expected output both times if the pipeline is deterministic).

if {[llength $argv] < 3} {
    puts "Usage: batch_run.tcl <bitstream.bit> <image_list_file> <results_file>"
    exit 1
}
set bitstream [lindex $argv 0]
set list_file  [lindex $argv 1]
set results_file [lindex $argv 2]
set probes_file [file rootname $bitstream].ltx

set FEATURE_BASE_ADDR       0x80000000
set COEFFICIENT_BASE_ADDR   0x80300000
set ADDR_AP_CTRL            0x00
set ADDR_FEATURES_DATA_0    0x10
set ADDR_FEATURES_DATA_1    0x14
set ADDR_COEFFICIENTS_DATA_0 0x1c
set ADDR_COEFFICIENTS_DATA_1 0x20

set DEC_BASE                0x1000
set DEC_AP_CTRL             [format "0x%x" [expr {$DEC_BASE + 0x00}]]
set DEC_FEATURES_DATA_0     [format "0x%x" [expr {$DEC_BASE + 0x10}]]
set DEC_FEATURES_DATA_1     [format "0x%x" [expr {$DEC_BASE + 0x14}]]
set DEC_CFG_DATA_0          [format "0x%x" [expr {$DEC_BASE + 0x1c}]]
set DEC_CFG_DATA_1          [format "0x%x" [expr {$DEC_BASE + 0x20}]]
set DEC_CFG_DATA_2          [format "0x%x" [expr {$DEC_BASE + 0x24}]]
set DEC_CFG_DATA_3          [format "0x%x" [expr {$DEC_BASE + 0x28}]]
set DEC_CFG_DATA_4          [format "0x%x" [expr {$DEC_BASE + 0x2c}]]
set DEC_CFG_DATA_5          [format "0x%x" [expr {$DEC_BASE + 0x30}]]
set DEC_CFG_DATA_6          [format "0x%x" [expr {$DEC_BASE + 0x34}]]
set DEC_CFG_DATA_7          [format "0x%x" [expr {$DEC_BASE + 0x38}]]
set DEC_CFG_DATA_8          [format "0x%x" [expr {$DEC_BASE + 0x3c}]]
set DEC_CFG_DATA_9          [format "0x%x" [expr {$DEC_BASE + 0x40}]]
set DEC_CFG_DATA_10         [format "0x%x" [expr {$DEC_BASE + 0x44}]]
set DEC_CFG_DATA_11         [format "0x%x" [expr {$DEC_BASE + 0x48}]]
set DEC_CFG_DATA_12         [format "0x%x" [expr {$DEC_BASE + 0x4c}]]
set DEC_CFG_DATA_13         [format "0x%x" [expr {$DEC_BASE + 0x50}]]
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
for {set attempt 1} {$attempt <= 8} {incr attempt} {
    after 2000
    refresh_hw_device -update_hw_probes true $dev
    set axi_core [lindex [get_hw_axis -of_objects $dev -quiet] 0]
    if {$axi_core ne ""} break
    puts "Debug hub/hw_axi not found yet (attempt $attempt/8), retrying..."
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
    # BUG FOUND (2026-10-29, batch-eval fork): a burst WRITE's -data list
    # lands in REVERSE order relative to ascending address -- confirmed
    # directly with a 4-word test ({deadbeef cafebabe 12345678 87654321}
    # written to ascending addresses read back as [87654321, 12345678,
    # cafebabe, deadbeef]). Mirrors the already-known reversal on the READ
    # side (axi_read_burst in scripts/jtag_full_frame_test.tcl), which
    # this session had already found and fixed -- the write side has the
    # same issue and was never checked by DDR readback until now, only by
    # downstream decoded output, which didn't obviously fail for the two
    # images tested earlier (not fully explained; flagged, not resolved,
    # in the final report). Fix: reverse each chunk before joining.
    set n [llength $words]
    set i 0
    while {$i < $n} {
        set chunk_len [expr {min(256, $n - $i)}]
        set chunk [lrange $words $i [expr {$i + $chunk_len - 1}]]
        set data_str [join [lreverse $chunk] "_"]
        set addr [format "0x%016x" [expr {$base_addr + 4 * $i}]]
        create_hw_axi_txn -force t_wb $core -address $addr -data $data_str -len $chunk_len -type write
        run_hw_axi [get_hw_axi_txns t_wb]
        incr i $chunk_len
    }
}

puts "Waiting 5s for automatic boot sequence..."
after 5000

# Decoder config is fixed/identity for every image -- write once.
axi_write1 $axi_core $DEC_CFG_DATA_0  65536
axi_write1 $axi_core $DEC_CFG_DATA_1  65536
axi_write1 $axi_core $DEC_CFG_DATA_2  0
axi_write1 $axi_core $DEC_CFG_DATA_3  0
axi_write1 $axi_core $DEC_CFG_DATA_4  0
axi_write1 $axi_core $DEC_CFG_DATA_5  0
axi_write1 $axi_core $DEC_CFG_DATA_6  524288
axi_write1 $axi_core $DEC_CFG_DATA_7  524288
axi_write1 $axi_core $DEC_CFG_DATA_8  0
axi_write1 $axi_core $DEC_CFG_DATA_9  0
axi_write1 $axi_core $DEC_CFG_DATA_10 0
axi_write1 $axi_core $DEC_CFG_DATA_11 0
axi_write1 $axi_core $DEC_CFG_DATA_12 0
axi_write1 $axi_core $DEC_CFG_DATA_13 0

set out [open $results_file w]
puts $out "number,pass,cnn_polls,cnn_ms,dec_polls,dec_ms,x,y,w,h,confidence,raw_objectness,valid_bit"
flush $out

set lf [open $list_file r]
set pairs {}
while {[gets $lf line] >= 0} {
    set line [string trim $line]
    if {$line eq ""} continue
    lappend pairs $line
}
close $lf

set total [llength $pairs]
set idx 0
foreach pair $pairs {
    incr idx
    lassign $pair number hexfile
    for {set p 1} {$p <= 2} {incr p} {
        puts "=== image $number pass $p ($idx/$total) ==="
        set fh [open $hexfile r]
        set lane_words [split [string trim [read $fh]] "\n"]
        close $fh
        axi_write_burst $axi_core $FEATURE_BASE_ADDR $lane_words

        set stale [axi_read1 $axi_core $ADDR_AP_CTRL]
        axi_write1 $axi_core $ADDR_FEATURES_DATA_0 $FEATURE_BASE_ADDR
        axi_write1 $axi_core $ADDR_FEATURES_DATA_1 0
        axi_write1 $axi_core $ADDR_COEFFICIENTS_DATA_0 $COEFFICIENT_BASE_ADDR
        axi_write1 $axi_core $ADDR_COEFFICIENTS_DATA_1 0
        set t0 [clock milliseconds]
        axi_write1 $axi_core $ADDR_AP_CTRL 0x00000001
        set polls 0
        set done 0
        while {$polls < 3000} {
            set ctrl [axi_read1 $axi_core $ADDR_AP_CTRL]
            if {[expr {($ctrl>>1) & 1}] != 0} { set done 1; break }
            incr polls
        }
        set cnn_ms [expr {[clock milliseconds]-$t0}]
        if {!$done} {
            puts $out "$number,$p,$polls,$cnn_ms,TIMEOUT,,,,,,,,"
            flush $out
            puts "  CNN TIMEOUT on image $number pass $p"
            continue
        }

        set stale2 [axi_read1 $axi_core $DEC_AP_CTRL]
        axi_write1 $axi_core $DEC_FEATURES_DATA_0 $FEATURE_BASE_ADDR
        axi_write1 $axi_core $DEC_FEATURES_DATA_1 0
        set t1 [clock milliseconds]
        axi_write1 $axi_core $DEC_AP_CTRL 0x00000001
        set polls2 0
        set done2 0
        while {$polls2 < 3000} {
            set ctrl2 [axi_read1 $axi_core $DEC_AP_CTRL]
            if {[expr {($ctrl2>>1) & 1}] != 0} { set done2 1; break }
            incr polls2
        }
        set dec_ms [expr {[clock milliseconds]-$t1}]
        if {!$done2} {
            puts $out "$number,$p,$polls,$cnn_ms,$polls2,$dec_ms,TIMEOUT,,,,,,"
            flush $out
            puts "  DECODER TIMEOUT on image $number pass $p"
            continue
        }

        set raw0 [axi_read1 $axi_core $DEC_BEST_O_DATA_0]
        set raw1 [axi_read1 $axi_core $DEC_BEST_O_DATA_1]
        set raw2 [axi_read1 $axi_core $DEC_BEST_O_DATA_2]
        set raw3 [axi_read1 $axi_core $DEC_BEST_O_DATA_3]
        set raw4 [axi_read1 $axi_core $DEC_BEST_O_DATA_4]
        set raw5 [axi_read1 $axi_core $DEC_BEST_O_DATA_5]
        set raw6 [axi_read1 $axi_core $DEC_BEST_O_DATA_6]

        puts $out "$number,$p,$polls,$cnn_ms,$polls2,$dec_ms,$raw0,$raw1,$raw2,$raw3,$raw4,$raw5,$raw6"
        flush $out
        puts "  OK: cnn=${cnn_ms}ms dec=${dec_ms}ms raw0=0x[format %08x $raw0] raw4(conf)=0x[format %08x $raw4] raw5(obj)=0x[format %08x $raw5] raw6(valid)=0x[format %08x $raw6]"
    }
}
close $out
puts "BATCH DONE"
close_hw_target
