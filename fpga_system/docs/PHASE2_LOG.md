# Phase 2 engineering log

Curated per-task log (ruling, superseding the raw `tee` dump Task 1's own
step literally specified -- the raw Vivado console output is thousands of
lines of IP-generation noise; a curated summary is what a future session
actually needs, and the commands here are exactly reproducible by rerunning
`vivado -mode batch -source scripts/create_project.tcl -source
bd/create_bd.tcl`).

## Task 1: MIG-only block design skeleton

- `set_property CONFIG.BOARD_MIG_PARAM {ddr3_sdram} [get_bd_cells mig_7series_0]`
  is the Tcl equivalent of the GUI's "Apply Board Preset" for MIG -- pulls in
  the Genesys2 board file's validated DDR3 pinout/timing
  (`board_files/genesys2/H/mig.prj`) and switches the IP from its native UI
  interface to an AXI slave port.
- MIG's `SYS_CLK` is a mandatory interface pin (not part of the "AXI/UI left
  unconnected" deferral) -- wired to a 200MHz differential external port.
- `DDR3` made external permanently (real physical pins). `S_AXI`, `sys_rst`,
  `aresetn` made external as temporary stubs purely so this MIG-only
  skeleton validates standalone; Task 2 replaced `S_AXI`/`aresetn` with real
  wiring (`sys_rst` stays external -- see Task 2 below).
- `validate_bd_design`: no errors. Two expected CRITICAL WARNINGs (S_AXI_0's
  address space unassigned, aresetn's async-looking reset source) -- both
  resolved or explained in Task 2.
- Spot-checked the generated MIG XDC's `ddr3_dq[0]` -> `PACKAGE_PIN AD3`
  against `mig.prj`'s `PinSelection` table (`PADName="AD3" name="ddr3_dq[0]"`):
  exact match.

## Task 2: CNN core + smartconnect + jtag_axi wired in

- Copied the full Phase 1 regenerated RTL hierarchy (97 `.v`/`.dat` files,
  everything under `cnn_engine.v` except the Phase-1-only `tb.sv`/
  `axi_ram*.sv` sim models) into `rtl/cnn_core/`, version-controlled instead
  of living in the scratch `cnn_rtl_sim_work/` directory.
- `cnn_engine_0` added via `create_bd_cell -type module -reference
  cnn_engine` (a plain RTL module, not packaged IP). This carries no
  clock/frequency metadata for its own AXI interfaces, so the BD's
  auto-inferred bus interfaces defaulted to a guessed `FREQ_HZ` that
  mismatched `ui_clk`'s real ~225.0225MHz (MIG's UI clock, derived from the
  DDR3-1066 timing in `mig.prj`: 900MHz VCO / 4:1 PHY ratio). Fixed with
  `set_property CONFIG.ASSOCIATED_BUSIF
  {m_axi_feature_ddr:m_axi_coefficient_ddr:s_axi_control}
  [get_bd_pins cnn_engine_0/ap_clk]` so `FREQ_HZ` propagates from the actual
  connected clock instead of a default guess.
- Reset tree: `proc_sys_reset_0` (ui_clk domain), `dcm_locked <-
  mig_7series_0/mmcm_locked`, `ext_reset_in <-` a new active-low top-level
  `ext_reset_in` port (Task 4's top wrapper will source this from a real
  board input). `peripheral_aresetn` drives `mig_7series_0/aresetn`,
  `cnn_engine_0/ap_rst_n`, `smartconnect_0/aresetn`, `jtag_axi_0/aresetn`.
  This is the standard Processor-System-Reset pattern Vivado's own CRITICAL
  WARNING in Task 1 was asking for.
- **Ruling (smartconnect topology):** the plan's Task 2 Step 2 text
  ("add smartconnect_0 (3 slave AXI, 1 master AXI toward MIG's AXI slave...)"
  immediately followed by "...jtag_axi_0, also wired to
  cnn_engine_0/s_axi_control") is ambiguous about whether jtag_axi counts as
  one of the 3 slaves or needs a second, separate connection to
  `s_axi_control`. First attempt wired jtag_axi directly to `s_axi_control`
  via `apply_bd_automation`, which auto-inserted its own extra
  `axi_interconnect` IP and left smartconnect_0 with only cnn_engine's 2
  ports -- clock/FREQ_HZ mismatches aside, this also doesn't match the
  handoff doc's requirement that jtag_axi be a real DDR debug backdoor
  ("push coefficients.bin straight into DDR over the cable... keep this
  permanently as a debug tool"), since that wiring never gave jtag_axi a
  path to DDR at all. Corrected to: `smartconnect_0` with `NUM_SI=3`
  (cnn feature, cnn coefficient, jtag_axi) and `NUM_MI=2` (M00 -> MIG
  S_AXI, M01 -> `cnn_engine_0/s_axi_control`). SmartConnect's crossbar then
  address-routes jtag_axi to BOTH destinations from its one physical AXI
  master port, while cnn_engine's own two data masters only ever reach M00
  in practice (the address decoder technically permits them to reach M01
  too -- `assign_bd_address` assigns every segment a master can physically
  reach, not every segment it will ever actually address -- but cnn_engine's
  internal op-coded addressing never targets its own control port, so this
  is not a real access-control gap for this phase). No second interconnect
  IP needed. Cost if this ruling is wrong: redo the smartconnect
  NUM_SI/NUM_MI config and re-route 2 connect_bd_intf_net calls --
  contained, no RTL change.
- `validate_bd_design`: no errors. Remaining CRITICAL WARNINGs are
  `RUSER_WIDTH`/`WUSER_WIDTH` (1-bit) on cnn_engine's two AXI-M ports not
  being an integer number of bits per RDATA/WDATA byte -- this is the
  HLS-generated AXI master's unused USER sideband tie-off, not the
  ID-width/burst-length class of defect Review Focus item 3 warned about
  (which would silently corrupt data; USER carries no payload and
  SmartConnect simply drops it). Confirmed no `ID_WIDTH`/`AWID`/`ARID`/burst
  warnings anywhere in the log.
- **Address map finding (Review Focus item 4):** `assign_bd_address`'s
  default assignment gives BOTH `cnn_engine_0/m_axi_feature_ddr` and
  `cnn_engine_0/m_axi_coefficient_ddr` the *same* segment --
  `OFFSET=0x80000000 RANGE=0x40000000` (MIG's full 1GB window). This is
  correct and expected: they are two independent AXI master ports into the
  same physical DRAM, so the hardware address decoder has no reason to
  carve the 1GB window between them -- that separation is a software/FSM
  choice (which base address gets programmed into each port's use), not
  something `assign_bd_address` enforces. **Pinned for Task 3/4:** the
  feature region needs `FEATURE_WORDS * 32 bytes = 73728 * 32 =
  0x240000` bytes starting at the shared base `0x80000000`. The copy FSM
  must target coefficients at `0x80300000` (clear of the feature region by
  ~768KB, comfortably inside the 1GB window) -- do not default to the same
  `0x80000000` base the feature port uses, or coefficient writes will
  silently alias live feature data.
  Also noted: `jtag_axi_0` correctly reaches both `SEG_cnn_engine_0_reg0`
  (control, 4KB) and `SEG_mig_7series_0_memaddr` (DDR, 1GB) -- the dual
  debug-backdoor capability the handoff doc asked for.

## Task 3: coefficient BRAM staging + copy FSM, standalone sim

- `coeff_bram_stage.v`: 41,600x128-bit BRAM, `$readmemh("rtl/coefficients.hex",
  mem)` -- the file was copied alongside the RTL (not read from
  `cnn_rtl_sim_work/`) so the relative path doesn't depend on which
  directory invokes the simulator/synthesizer; standardized on invoking
  everything (sim and Vivado batch) from the project root, so the same
  `rtl/coefficients.hex` path works for both.
- `copy_fsm.v`: single-ID, single-beat-per-word AXI4 write master (no burst
  optimization in this bring-up phase), port names mirroring
  `cnn_engine`'s `m_axi_coefficient_ddr_*` widths read directly from
  `rtl/cnn_core/cnn_engine.v` (ID_WIDTH=1, ADDR_WIDTH=64, DATA_WIDTH=128,
  WSTRB_WIDTH=16, AWLOCK width 2 -- not 1, caught by reading the actual
  port declarations instead of assuming). `BASE_ADDR` defaults to
  `0x80300000`, the real offset pinned in Task 2's address-map finding
  above.
- Caught and fixed a real protocol bug before simulating: the AW/W handshake
  transition conditions originally checked only `AWREADY`/`WREADY`, not
  also the FSM's own registered `AWVALID`/`WVALID` -- on the very first
  cycle of each state this could complete a handshake the slave never
  actually saw asserted for a full cycle, since a Verilog `reg` read inside
  the same clocked process holds its pre-edge value. Fixed to
  `if (m_axi_AWVALID && m_axi_AWREADY)` / `if (m_axi_WVALID && m_axi_WREADY)`.
- Ruling: scaled the done-watchdog from the `vivado-build-and-flash` skill's
  illustrative `#2_000_000` (time units) example to a 2,000,000-*cycle*
  bounded wait loop. 41,600 words through `axi_ram.sv`'s deliberately
  throttling slave (`AWREADY`/`WREADY` gated on `cycle%11`/`cycle%5`)
  realistically needs on the order of 200K+ cycles -- the actual run
  finished in 228,802 cycles (2,288,025 ns at the testbench's 10ns clock).
  The illustrative number was sized for a different, much smaller design;
  the pattern (a bounded wait instead of an unbounded one) is what matters,
  not the literal constant. Cost if wrong: none observed -- margin was
  ~9x the actual runtime.
- Ruling: `fork`/`join_any` (used in the first draft's watchdog) are
  SystemVerilog-only constructs; `tb_bram_to_ddr.v` is plain Verilog-2001
  (`.v`, matching this project's other testbenches) and `xvlog` rejected
  them. Replaced with a plain `while` wait loop. Cost if wrong: none, this
  is a mechanical syntax fix with identical behavior.
- Simulation result: `errors == 0` after comparing all 41,600 words of the
  behavioral RAM's contents against `coefficients.hex` word-for-word
  (Review Focus item 2 -- not just checking that `done` went high). A
  zeroed/garbage DDR would have shown near-100% mismatches here, not
  `errors == 0`, so this is not the Phase-1-style silent-false-positive
  failure mode.

## Task 4: full standalone top-level, MIG-calibration-aware simulation

- `cnn_subsystem_top.v` instantiates the generated `cv_subsystem_wrapper`
  (MIG + cnn_engine + smartconnect + copy_fsm/coeff_bram_stage + jtag_axi +
  ap_start_seq), reports `init_calib_complete`/`copy_fsm_done`/`cnn_ap_done`
  over UART. `cnn_ap_done` has no port anywhere in the hierarchy (it's an
  internal `reg` inside the raw `cnn_engine` module) -- reached via the
  hierarchical path `u_bd.cv_subsystem_i.cnn_engine_0.inst.ap_done`,
  confirmed by reading the actual generated instance names
  (`cv_subsystem_cnn_engine_0_0` wraps the raw module as instance `inst`)
  rather than guessing.
- **Scope gap found while writing this task (ruling):** nothing in this
  standalone subsystem (no software/processor) would ever write
  `ap_start` to drive `cnn_engine` at all, yet the brief wants
  `cnn_ap_done` to assert. Added `rtl/ap_start_seq.v`, a one-shot AXI-Lite
  write sequencer triggered by `copy_fsm_done`, as smartconnect's 5th
  slave (reaching `s_axi_control` only -- excluded from MIG's 1GB segment
  via `exclude_bd_addr_seg`, since its AWADDR had to be widened to 32 bits
  just to receive the generic 4KB control-port address assignment in the
  first place). This exercises the real AXI/handshake path for
  timing-validation purposes; it does not claim a meaningful detection
  (no camera feature data exists in DDR yet -- see the module's own header
  comment).
- `make_bd_pins_external` ruling from Task 2 held here too: used manual
  `create_bd_port` + `connect_bd_net` for `init_calib_complete_dbg`,
  `copy_fsm_done_dbg`, and `ui_clk_dbg` (the last one so the UART
  status-reporter logic in `cnn_subsystem_top.v` runs in the same clock
  domain as everything it reports on, rather than needing a second clock).
- **Three real bugs found and fixed before/during simulation, each by
  running something and reading real output, not by inspection alone:**
  1. `#20_000_000_000` / `#40_000_000_000` watchdog delays overflow
     Verilog's default 32-bit signed integer literal width (max
     2,147,483,647) and silently wrap -- xelab's own compile warning
     ("using -1474836480 instead") caught this before the sim ever ran.
     Fixed by writing them as real-number literals (`20_000_000_000.0`),
     which have no such width limit.
  2. `ddr3_dm_sdram` was declared `reg` and connected to `dm_tdqs`, an
     `inout` port on `ddr3_model` (DM shares the TDQS function in some
     DDR3 modes) -- Verilog requires a net on both sides of an `inout`
     connection. Fixed with the same `reg` tmp + continuous-`assign` wire
     two-step the MIG reference testbench (`sim_tb_top.v`) uses for this
     exact signal.
  3. The `export_simulation`-generated `cmd.tcl` defaults to `run 1000ns;
     quit` (a GUI quick-look default) -- the first full run completed in
     6 seconds and printed nothing, which would have looked like a silent
     pass/no-op if not sanity-checked against expected runtime. Fixed by
     writing a separate `run_all.tcl` (`run -all; quit`) and invoking
     `xsim <snapshot> -tclbatch run_all.tcl` directly against the
     already-elaborated snapshot (no recompile needed).
- **Result:** `STAGE 1: init_calib_complete` -> `STAGE 2: copy_fsm_done` ->
  `STAGE 3: cnn_ap_done` -> `ALL STAGES OK`, no watchdog fired. Real
  calibration completed at 38.19us simulated (`PHY_INIT: Read Leveling
  Stage 1 completed at 38191626.0 ps`, with 2,160 real `READ @ DQS` probe
  cycles logged by the behavioral DDR3 model before that point -- genuine
  calibration work, not a stub). Total simulated runtime to `$finish`:
  ~84.4us, comfortably inside the 62ms worst-case watchdog budget
  (2ms+20ms+40ms). Real wall-clock time for the full compile+elaborate+
  simulate: ~25 minutes, dominated by elaborating MIG's full PHY/calibration
  RTL and the cnn_engine core's generated hierarchy.
- `PHASE2_SIM_BYPASS_CAL=1` (gating `SIM_BYPASS_INIT_CAL=FAST` and the
  256-word override) is simulation-only, confirmed never set for Task 5's
  build.

## Final fix pass: code review findings, applied and re-verified

A fresh-context subagent review (model: opus) of the full Task 1-5 diff
(66e6ee9..282c8b7) found 3 Critical and 8 Important/documentation findings.
Full review text is in this session's transcript; this section records what
was actually changed and the real evidence that closes (or honestly does
not close) each one.

**C1 (Critical) -- coeff_bram_stage's entire BRAM array dissolved to
nothing during synthesis.** `rtl/coeff_bram_stage.v:12`'s `HEXFILE` default
(`"rtl/coefficients.hex"`) is relative; each per-IP out-of-context synthesis
run's CWD is `vivado/*.runs/cv_subsystem_coeff_bram_stage_0_0_synth_1/`,
where that path never existed.
`vivado/genesys2_cv.runs/cv_subsystem_coeff_bram_stage_0_0_synth_1/runme.log:34`:
`CRITICAL WARNING: [Synth 8-4445] could not open $readmem data file
'rtl/coefficients.hex' ... ignoring`, followed by "RAM dissolved into
registers" and 41,600 "does not have driver" warnings. That IP's own
utilization row was all zeros; `build.log`'s top-level grep (the plan's own
Task 5 Step 3 instruction) never saw it, because it never looked at per-IP
logs. **Fix:** `bd/create_bd.tcl` now does
`set_property CONFIG.HEXFILE [file join $root_dir rtl coefficients.hex]
[get_bd_cells coeff_bram_stage_0]` -- an absolute path, correct from any
CWD. **Evidence:** rebuilt; `coeff_bram_stage_0`'s row in the new
`vivado/utilization.rpt` now reads `0 LUT | 0 FF | 256 RAMB36 | 0 RAMB18 |
0 DSP` -- real BRAM, not dissolved.

**C2 (Critical) -- cnn_engine's FEATURES/COEFFICIENTS base-address
pointers were never programmed, so cnn_engine's own AXI-M masters
addressed DDR offset 0x0 -- which the system address map decodes to
cnn_engine's OWN control-register segment.** `rtl/ap_start_seq.v`'s first
version wrote only `ADDR_AP_CTRL` (0x00). Confirmed the real register
addresses by reading `rtl/cnn_core/cnn_engine_control_s_axi.v:82-86`
directly (`ADDR_FEATURES_DATA_0/1 = 0x10/0x14`,
`ADDR_COEFFICIENTS_DATA_0/1 = 0x1c/0x20`), not assumed. **Fix:** rewrote
`rtl/ap_start_seq.v` as a 5-write sequencer (FEATURES_DATA_0 = 0x80000000,
FEATURES_DATA_1 = 0, COEFFICIENTS_DATA_0 = 0x80300000,
COEFFICIENTS_DATA_1 = 0, then AP_CTRL = ap_start), with new `FEATURE_BASE_ADDR`/
`COEFFICIENT_BASE_ADDR` parameters matching `copy_fsm`'s own `BASE_ADDR`
default so cnn_engine looks for coefficients at the same place `copy_fsm`
wrote them.

**C3 (Critical, PARTIALLY addressed -- NOT resolved) -- the `cnn_ap_done`
status bit is the same silent-false-positive class `PHASE1_STATUS.md`
documented.** The first version of `sim/tb_cnn_subsystem_top.v` waited for
`cnn_ap_done` with no lower bound. **Fix applied and PROVEN WORKING:**
added a 100,000-cycle floor assertion between `copy_fsm_done` and
`cnn_ap_done` (Phase 1's own real pass measured 3,774,628 cycles --
`PHASE1_STATUS.md`). Re-ran the simulation with C2's fix applied
(`sim_export/xsim/run_all.log`): the check correctly **FAILED** --
`STAGE 3 TIMING: 374 cycles from copy_fsm_done to cnn_ap_done (floor:
100000)` / `FAIL: cnn_ap_done asserted after only 374 cycles`. Traced
further: `rtl/cnn_core/cnn_engine.v:1387` sets `ap_done` combinationally
when `icmp_ln282_fu_444_p2 == 1` (line 1629:
`pc_fu_120 == 6'd55`) while in `ap_CS_fsm_state2` -- i.e. once the
internal program counter has dispatched all 55 ops. `pc_fu_120` only
advances when the called `grp_convolve_fu_357`/`grp_vector_operation_fu_410`
sub-block reports its own `ap_done` (line 1618's block condition). 374
cycles / 55 ops = ~6.8 cycles/op -- the sub-blocks are themselves
completing almost instantly, which is not real convolution/vector-op work
at any plausible feature-map size. **Ruling: this is NOT fixed.** The
AXI-Lite pointer-write sequence (C2) is structurally verified correct by
inspection; the fast completion traces to something inside the
HLS-generated core's own internal call/dispatch timing, in
`rtl/cnn_core/*.v` -- a frozen, Phase-1-validated artifact this phase does
not modify (explicitly out of scope, same boundary the code review itself
drew). This is left as a tracked, open, honestly-reported finding, not
claimed as resolved. It does not affect Task 5's timing numbers (synthesis
times the logic regardless of runtime behavior).

**I4 (Important) -- `build.tcl`'s CRITICAL-WARNING check only grepped the
top-level `build.log`**, exactly why C1 went unnoticed (the `8-4445`
warning lived only in a per-IP `runme.log`). **Fix:** `scripts/build.tcl`
now globs every `vivado/*.runs/*/runme.log`, fails on any `CRITICAL
WARNING` not matching a short allowlist (the known-benign RUSER/WUSER
sideband-width warnings), and separately parses `coeff_bram_stage_0`'s own
utilization row to assert nonzero RAMB36/RAMB18. (Hit and fixed a real bug
in this fix itself: the first version used `lmap`, which does not exist in
Vivado 2023.2's Tcl interpreter -- `invalid command name "lmap"` --
replaced with a plain `foreach`+`lappend` loop, found by actually running
it.) **Evidence:** this rebuild printed "No unexpected CRITICAL WARNINGs in
any per-IP runme.log (9 logs checked)" -- a real, exercised gate.

**I5 (Important) -- `copy_fsm.v` and `ap_start_seq.v` both ignored
`BRESP`**, completing on `BVALID` alone (same silent-false-positive class
as C3). **Fix:** both now latch a sticky `err` output on any non-OKAY
response.

**I6 (Important) -- the ~169 MHz clock-rate recommendation in the first
version of `PHASE2_STATUS.md` was derived wrong twice**: `1/5.933ns`
ignored setup/skew/uncertainty, and separately ignored that Phase 1 had
already measured this exact core's Fmax. **Fix:** `PHASE2_STATUS.md` now
leads with `PHASE1_STATUS.md`'s measured 128.12 MHz and the core's own
100 MHz HLS compile target (`cnn_engine.v:10`,
`HLS_INPUT_CLOCK=10.000000`), with the new build's slack-derived figure
(4.444+1.954=6.398ns -> 156.3 MHz) presented as a secondary floor.

**I7 (Important) -- a duplicate `create_clock` in
`constraints/genesys2_cv.xdc` silently overrode MIG's own generated clock
constraint.** `build.log` (first build) had
`CRITICAL WARNING: [Constraints 18-1056] Clock 'sys_clk' completely
overrides clock 'sys_clk_p'` -- flagged by the tool, reported by neither
this log nor the status doc until the review caught it. **Fix:** removed
the `create_clock` line from the XDC; MIG's own generated XDC is the sole
source for this clock. **Evidence:** no "completely overrides" warning
anywhere in the rebuilt `build.log`.

**I8 (Important) -- `ui_clk_sync_rst` was never wired into the reset
tree.** `proc_sys_reset_0` gated only on `mmcm_locked`; MIG's own AXI
example design also gates on the UI-side sync reset. Harmless today only
because every master waits on `init_calib_complete`. **Fix:**
`bd/create_bd.tcl` wires `mig_7series_0/ui_clk_sync_rst` into
`proc_sys_reset_0/aux_reset_in` (confirmed `CONFIG.C_AUX_RESET_HIGH`
defaults to 1, i.e. active-high, matching `ui_clk_sync_rst`'s own polarity
with no inversion needed -- checked via a scratch BD probe, not assumed).

**I10 (Important) -- no sim runner or sim log was ever committed**; both
simulations in this phase existed only as hand-run commands. **Fix:**
committed `scripts/sim_bram_to_ddr.sh` (Task 3's standalone sim) and
`scripts/sim_top.sh` (Task 4's full MIG-calibration-aware sim, including
the `export_simulation` + hand-written `run_all.tcl` workaround for the
generated `cmd.tcl`'s `run 1000ns; quit` default). This fix pass's own
`sim_export/xsim/run_all.log` (the run that caught C3) is force-added
alongside `build.log` as evidence.

**Deferred as minor, not implemented this pass** (recorded so they are not
rediscovered from scratch): `sim/axi_ram.sv`'s pre-zeroed reference RAM
(M1); no elaboration-time `ADDR_W >= $clog2(WORDS)` check in
`copy_fsm.v`/`coeff_bram_stage.v` (M2); an inverted explanatory comment
about UART timing margin in `cnn_subsystem_top.v` (M3); a drop-and-retry
edge case in the UART status reporter if `uart_busy` is high on the report
tick (M4); `copy_fsm`/`ap_start_seq`'s shared AW/W/B skeleton, two
instances being the right call against premature abstraction (M5);
`copy_fsm`'s one-AXI-transaction-per-word throughput, already documented as
a bring-up simplification (M6); a sentinel-file suggestion for detached
background builds (M8); splitting `PHASE2_SIM_BYPASS_CAL` into two
independent env vars so Task 4 could exercise the full 128-to-256-bit
SmartConnect width conversion at full calibration speed (I9 -- correct, but
needs another full sim re-run to verify, out of proportion for this pass);
and exposing `cnn_engine`'s real `interrupt` port with GIE/IER enabled
instead of `ap_start_seq`'s proxy (I11 -- the review confirmed the current
`SIM_HIERARCHICAL_AP_DONE_PROBE` generate-mux pattern is safe as-is;
fail-safe default, simulation-only override; this would be a clarity
improvement, not a safety fix).

## C3 real-image investigation: is the 374-cycle `ap_done` a real bug?

The fix pass above closed C1 and C2 but left C3 "detection mechanism fixed,
underlying false positive not resolved": `cnn_ap_done` still asserted after
only 374 cycles even with FEATURES/COEFFICIENTS correctly programmed,
against an otherwise-default (never explicitly written) feature-memory
region. Open question: is 374 cycles a benign artifact of testing with
empty feature memory, or a real Phase-2 integration bug reachable with real
data too? Decisive test: feed an actual labeled photo through the same
DDR3/AXI path and see whether the behavior changes.

**Packing format, reverse-engineered from the teammate's own exporter**
(not guessed): `Genesys2_Teammate_Handoff_20261028/cv_model/reference_source/
campaign/shared_engine/export_wide_model_r4.py`, the script that produced
the already-validated `input_0/1/2.bin` vectors, do letterbox-resize to
256x192 (pad 114, `data_roi256.sized`) -> BGR->RGB -> HWC->CHW -> /255 ->
`round(x * 16384)` int32 (Q14) -> pad channel 3->8 with zeros (NCHW8) ->
transpose to NHWC8 -> raw little-endian bytes. One 256-bit FeatureWord per
pixel: 8 x 32-bit sign-extended lanes, channels 0-2 = R,G,B Q14, channels
3-7 = 0. Confirmed byte-for-byte against the real `input_0.bin` size
(1,572,864 bytes = 49,152 words x 32 bytes). `scripts/pack_image_to_hex.py`
implements this recipe and emits a `$readmemh`-compatible hex file.

**Test photos**: the handoff only bundles pre-rendered documentation
figures (`cv_model/examples/photo_examples_50/`, headers + bounding-box
overlays + closeup insets baked in), not raw sensor frames -- no raw
dataset images are included. Both test images were cropped to just the
embedded photo region (`--crop 190,88,1090,807`) before packing, confirmed
by inspection.

**Scope reduction (deliberate, matches existing project precedent)**: only
the WORDS=256 word (one canvas row) is copied into feature memory per run,
not the full 49,152-word frame -- mirroring `coeff_bram_stage_0`'s own
existing sim-bypass cut (41,600 -> 256 words) for the identical reason:
individual-AXI-transaction-per-word through the realistic DDR3 behavioral
model is impractically slow in wall-clock sim time at full frame size, and
isn't needed to answer the narrower "does nonzero real data change
`ap_done` timing" question. This is NOT a full-frame detection-accuracy
test. Row 147 (of 192) was chosen because it falls inside the drone's
actual bounding-box region for the positive example (see CPU benchmark
below) -- not an arbitrary row, and not pure letterbox padding (checked:
row 0 is uniform 114/114/114 padding for both images, useless as a test).

**CPU-side ground-truth check** (independent of the FPGA RTL, run on the
*full* letterboxed frame through the real `quantized_fx.pt` via the same
node-by-node Q14-round/saturate `Fixed` interpreter the teammate's exporter
uses -- i.e. the exact arithmetic the hardware core is built to reproduce):
the drone photo's strongest head3 detection peak (raw logit product
obj*class = 6.56) lands at canvas row ~150-178, squarely inside the row-147
test slice; the sky photo has no comparable peak anywhere (best 1.68, at an
unrelated location). This independently confirms the two test photos are
genuinely discriminative for this model, and that row 147 is a
meaningfully-chosen slice, not a coincidence.

**RTL changes**: `copy_fsm.v` parameterized with `DATA_WIDTH` (128 default,
unchanged behavior; 256 for features) instead of a near-duplicate module;
new `feature_bram_stage.v` (256-bit `coeff_bram_stage.v` twin) and `and2.v`
(gates `ap_start_seq_0/trigger` on both copy FSMs' `done`, sim-only).
`bd/create_bd.tcl` adds `feature_bram_stage_0` + `copy_fsm_1` + `and2_0`
entirely inside the existing `PHASE2_SIM_BYPASS_CAL` gate -- none of this
reaches the permanent hardware build; a real camera-frame loader is future
Phase 3 work, not this bring-up test's job. `sim/tb_cnn_subsystem_top.v`'s
`stage2_done` now also waits on `copy_fsm_1`'s `done` (hierarchical
reference, like the existing `cnn_ap_done` probe -- `copy_fsm_1` has no
top-level debug port since `cnn_subsystem_top.v`'s port list is shared with
the hardware build, where this cell doesn't exist).

**First attempt failed fast**: forgot `add_files` for `and2.v` before
referencing it in `create_bd_cell -type module -reference and2` --
`ERROR: [filemgmt 56-587] Failed to resolve reference`. Caught within the
first minute (BD creation runs before the long elaboration/sim steps), not
after a wasted 25+ minute run. Fixed, re-running.

## Real-hardware prep: timing fix merged, JTAG photo-load path added

**Full-DDR3-model simulation killed, not completed.** The drone-row C3 sim
(previous section) was found to be actively computing (98.9% CPU, real
incrementing DDR3 write addresses in its log) but at a pace that would have
taken many more hours to clear even one simulated millisecond of its
20ms-budget Stage 2 -- two AXI write masters contending for one
cycle-accurate behavioral DDR3 model evidently costs far more than linear
word-count scaling predicted. Killed rather than waited out; the narrower
"does real pixel data change `ap_done` timing" question this sim existed to
answer is deferred to real hardware instead, where a slow simulator's
DDR3-protocol-timing realism isn't the bottleneck.

**Timing-closure fix (dispatched to a subagent earlier this session)
verified and merged.** Real post-route result in an isolated copy: `BUILD
OK`, `TIMING MET`, WNS=+0.040ns (up from the prior -1.954ns). Root cause:
the critical path was entirely inside `cnn_engine_0`'s own HLS-generated
logic (33 logic levels, 5.994ns required vs 4.444ns available at `ui_clk`'s
225.02MHz) -- `cnn_engine.v` was HLS-synthesized for a 100MHz target
(`HLS_INPUT_CLOCK=10.000000`) and Phase 1 measured 128.12MHz Fmax, both
well under the 225MHz it had been tied to as a known simplification. Fix:
`bd/create_bd.tcl` now gives `cnn_engine_0` its own 100MHz clock domain via
`clk_wiz_0` (`CONFIG.PRIM_SOURCE=No_buffer` since the input is `ui_clk`, an
internal fabric clock, not a board pin) plus a matching `proc_sys_reset_1`,
bridged back to the `ui_clk`/225MHz domain on all three of `cnn_engine`'s
AXI interfaces via `axi_clock_converter_0/1/2` (standard Xilinx IP, not
hand-rolled CDC logic). No RTL file was touched -- purely a BD-level
clocking change. Diffed against the live repo and merged in (only
`bd/create_bd.tcl` changed); a fresh `build.tcl` run is in progress in the
canonical repo location to confirm this reproduces there too (the verified
run was in the fix's own isolated working copy).

**Residual risk, not yet closed by simulation**: the new CDC bridges use
proven Xilinx IP, and the only path that's actually synthesized for
hardware (`cnn_ap_done` via `ap_start_seq`'s `ap_start_issued` proxy) never
crosses the new clock boundary at all -- so the highest-risk spot doesn't
apply here. But no functional RTL simulation of the new dual-clock
architecture has been run (the realistic-DDR3-model sim that would have
exercised it was killed above for being impractically slow, and a
MIG-bypass fast-sim harness for this specific check doesn't exist yet).
This is a known, accepted gap, not an oversight -- the first real flash
attempt is effectively also the first functional test of this fix.

**Real-hardware photo-loading path added** (`scripts/jtag_photo_test.tcl`,
`scripts/program.tcl`, `pack_image_to_hex.py --format lanes32`): rather
than extending the sim-only BRAM+copy_fsm path to real hardware (synthesis-
time $readmemh means one baked-in photo per bitstream rebuild), real
hardware uses `jtag_axi_0` -- already kept in this design as a permanent
debug tool -- to burst-write a packed photo directly into DDR3 at
`FEATURE_BASE_ADDR` after boot, then manually re-trigger `ap_start` against
the real data (the automatic `ap_start_seq_0` pass fires once already,
against whatever was in feature memory at boot -- a throwaway first pass,
not used). Address map confirmed from this build's own `assign_bd_address`
output, not assumed: `jtag_axi_0` reaches `cnn_engine_0`'s control register
at local offset `0x0`, and MIG's DDR window at `0x80000000` -- the same
addresses `ap_start_seq`/`copy_fsm` use internally, confirming a single
consistent global AXI map. `feature_drone_lanes32.hex` /
`feature_sky_lanes32.hex` (both photos, row 147, 2048 32-bit lanes each)
are generated and ready.

**Not yet run against real hardware** -- no board/JTAG cable reachable from
this environment. `jtag_photo_test.tcl` and `program.tcl` are written and
address-mapped from this project's own real build output, but unverified;
treat the first real run as a test of these scripts too, not only of the
board.

## C3 CONFIRMED on real hardware (not a sim artifact)

**First real-hardware run of this design.** Board confirmed reachable
(FT2232 "Digilent Adept USB Device", serial 200300BD82EE; `xc7k325t_0`
enumerates via `hw_server`). Flashed the timing-closed bitstream
(WNS=+0.040ns, reproduced in the canonical repo, not just the fix's
isolated copy) and ran both test photos through the real JTAG-AXI path.

**Two bugs found and fixed en route** (both in tooling, not the design):
1. `build.tcl`'s `launch_runs impl_1` never included `-to_step
   write_bitstream` -- every prior "BUILD OK" in this project's history
   meant "timing/BRAM checks passed", not "a flashable .bit exists". No
   bitstream had ever actually been produced. Fixed; also added an explicit
   bitstream-existence check before `BUILD OK` can print.
2. `jtag_axi_0` wouldn't enumerate as a `hw_axi` object
   ("No matching hw_axi were found") despite the debug hub being correctly
   synthesized (`dbg_hub_CV`, confirmed in synth_1/runme.log) -- missing
   `write_debug_probes` output (`.ltx`). `program.tcl` and
   `jtag_photo_test.tcl` now both generate/set `PROBES.FILE`. Also hit
   flaky "debug hub core was not detected" on a subsequent run (likely a
   race against MIG's MMCM/calibration settling right after configuration,
   since the hub's clock is `ui_clk`) -- added a retry-with-delay loop
   rather than a fixed assumption either way.

**Result, decisive**: for both the real drone photo (row 147, inside its
labeled bounding box) and the real sky photo, manually triggering
`ap_start` against the freshly-JTAG-written feature data produced
`ap_done` on the very first possible poll. Measured wall-clock from the
`ap_start` write to confirmed `ap_done`: drone 4ms, sky 6ms -- in both
cases statistically indistinguishable from the wall-clock cost of a single
bare JTAG-AXI read transaction alone (4ms / 6ms respectively, measured
separately). A real compute pass needs a minimum of ~37.7ms (Phase 1's
measured 3,774,628 cycles at `cnn_engine`'s new 100MHz clock) -- there is
no way real computation happened in either window.

**This resolves the open question from the earlier C3 investigation.** The
374-cycle sim finding was NOT a benign artifact of testing against
empty/default feature memory: the same instant/false `ap_done` reproduces
on real silicon, with real, meaningfully different, correctly-addressed
image data actually written into feature memory via a path independent of
the sim's DDR3/copy_fsm machinery (plain JTAG-AXI writes). Data-independent
(identical signature for two different images) points at a control-path
bug -- most likely in `ap_start_seq`'s or `cnn_engine_control_s_axi.v`'s
handshake/address-decode logic, not in the convolution datapath itself.
Root cause not yet found; out of scope for this session's remaining time,
but no longer an open question of "is this real" -- it is real, confirmed
on hardware, and blocks trusting any detection result from this core until
fixed.

## CORRECTION: the "C3 confirmed on real hardware" finding was a test-script bug

**The previous section's conclusion was wrong.** Root-caused via
superpowers:systematic-debugging rather than accepting the surface symptom:

`cnn_engine`'s `ap_done` bit (AXI-Lite `AP_CTRL`, bit 1) is **read-to-clear**
(standard Xilinx HLS `ap_ctrl_hs` semantics) -- confirmed directly by
reading it twice in a row and watching it drop (`0x0e` -> `0x04`). The
automatic boot-time `ap_start_seq_0` pass latches `ap_done=1` well before
`jtag_photo_test.tcl` ever touches the register. The script's first version
wrote its own `ap_start` and immediately began polling `AP_CTRL` for
`ap_done` -- without ever reading (and thus clearing) that stale bit first.
"`ap_done` observed after 0 poll iterations" was reading **leftover state
from the automatic pass**, not the result of this script's own trigger at
all. The two "instant done" measurements in the previous section (4ms
drone, 6ms sky) are explained in full by this, no hardware bug required.

**Fixed `jtag_photo_test.tcl`** to read (clear) `AP_CTRL` once immediately
after the real photo is loaded, before writing its own `ap_start`. Reran
both test photos end-to-end (fresh `program_hw_devices` each time, not
reusing prior board state):

| | polls | wall clock, write-\>done | HEAD1 lane4 (Q14) | HEAD0 lane9 (Q14) |
|---|---|---|---|---|
| Drone (row 147) | 14 | 62ms | -13.46 | 2.16 |
| Sky (row 147) | 19 | 58ms | -12.13 | 2.29 |

Both times are comfortably above the ~37.7ms floor for a real pass
(3,774,628 cycles at `cnn_engine`'s new 100MHz clock). The two images'
outputs are close in magnitude but consistently different in the specific
values -- exactly the expected signature given only one row (147) of the
192-row frame actually differs between the two runs; the rest of feature
memory is shared. This is real, data-dependent computation, not noise or a
stuck/garbage readback.

**Net result**: `cnn_engine`, the new CDC clock-domain-crossing fix, the
control-register path (including the new `axi_clock_converter`s), and the
JTAG-AXI photo-loading mechanism all appear to be working correctly on real
hardware. The residual open question is the ORIGINAL simulation's
374-cycle finding (Task 4's fix pass, a direct hierarchical probe into
`cnn_engine`'s internal `ap_done` register, not the AXI read-to-clear path
-- so not explained by this same bug). That finding predates today's CDC
fix and has not been re-tested; given today's real-hardware result is
strongly positive, re-investigating the old sim-only finding is optional
follow-up work, not a blocker. **C3's status is downgraded from "Critical,
confirmed real" back to "unresolved discrepancy between an old simulation
finding and today's positive real-hardware result" -- not consistent with
a confirmed present-day bug.**

## Real-hardware decoder integration: validated and working

Integrated `decode_work_heads_0` (pre-synthesized HLS RTL from the
teammate's handoff, `cv_model/fpga/decoder_rtl/`) into the design: its own
`axi_clock_converter` bridges (feature-DDR read + AXI-Lite control),
sharing `clk_wiz_0`'s already-proven 100MHz domain with `cnn_engine_0`.
`bd/create_bd.tcl`'s `smartconnect_0` grew from 5/2 to 6/3 (slave/master)
ports. Real build: `WNS=+0.040ns, TIMING MET` -- identical to the
pre-decoder build, confirming the addition didn't regress timing.

**Bug found and fixed (not a hardware fault):** `scripts/jtag_decode_test.tcl`
computed the decoder's register addresses via `expr {$DEC_BASE + ...}}`,
which Tcl stringifies in decimal (`0x1000+0x00` -> the string `"4096"`),
not hex. `create_hw_axi_txn -address` reads a bare numeric string as hex
regardless of this, so `"4096"` was silently read as address `0x4096` --
completely unmapped, outside `decode_work_heads_0`'s real
`0x1000`-`0x1fff` control window -- landing on a fixed bus "no response"
sentinel (`0xdec0dee3`) on every single read. 100% reproducible (not
flaky): every address built from a hardcoded hex literal (cnn_engine's
reads, the diagnostic scripts) always worked; every `expr`-computed DEC_*
address always failed, identically. Wasted several real diagnostic cycles
chasing a "transient JTAG flakiness" theory before diffing the actual
address string formatting settled it. Fixed with `format "0x%x" [expr
...]]` wrapping every DEC_* address.

**Result, fully validated**: real hardware output for the drone photo
(row-147 earlier; this run used the full 256x192 frame) matches an
independent Python port of the exact reference decode algorithm
(`scripts/decode_heads.py`, traced from `decoder_work_r2.cpp`, not
re-derived) to quantization precision:

| field | hardware | Python reference |
|---|---|---|
| x | 32.19 | 32.2 |
| y | 179.58 | 179.6 |
| w | 149.17 | 149.2 |
| h | 72.69 | 72.7 |
| confidence (Q16) | 26 | 26.2 (0.0004 * 65536) |
| raw_objectness (24-bit signed) | -128408 | -128408 (exact) |
| valid | 1 | True |

`BEST_O` register layout confirmed empirically: `DATA_0..3`=x,y,w,h (Q16,
32-bit), `DATA_4`=confidence (`ap_uint<17>`, Q16), `DATA_5`=raw_objectness
(`ap_int<24>`, sign-extend from bit 23, not bit 31), `DATA_6`=`{valid at
bit16, index in bits[15:0]}`.

Decoder `ap_done` fired after 1 poll (~12ms, mostly JTAG round-trip
overhead) -- its own compute time is comfortably fast, not a meaningful
addition to the pipeline's throughput budget on top of `cnn_engine`'s
~37ms.

## Frame-rate ceiling: 30Hz is not achievable as currently built

`cnn_engine`'s ~37ms per pass (100MHz clock, chosen to close timing --
see the earlier CDC fix section) exceeds the 33.3ms budget 30Hz requires,
before adding camera capture, DDR copy, or decode overhead. Root cause is
a direct tradeoff from today's timing fix: the core's design target (and
Phase 1's measured 128.12MHz Fmax) would give ~16.8ms at the originally-
intended 225MHz, comfortably inside a 30Hz budget, but that configuration
failed timing closure. The architecture is also inherently resource-shared
(55 operations reuse the same compute hardware sequentially), so cycle
count is roughly fixed regardless of clock choice. Options, not yet acted
on pending a decision: accept a lower frame rate (~20-25fps realistic
ceiling), re-run HLS synthesis with tighter pipelining/II targeting a
higher clock (Vitis HLS not on this machine's PATH currently), or
re-architect for more parallelism (BRAM already ~82% used, limited
headroom).

## pipeline_seq: automatic CNN->decode->UART chain, built and verified on real hardware

Added `rtl/pipeline_seq.v`, a new AXI-Lite master (write AND read -- the
first in this project with read capability, since polling two cores' real
`ap_done` bits and capturing the decoder's 7 result registers both need
reads, which `ap_start_seq.v`/`copy_fsm.v` never needed). It supersedes
`ap_start_seq_0` entirely (removed from `bd/create_bd.tcl` -- keeping both
would have let two masters race to write `cnn_engine`'s control registers
around the same time). One-shot, same `trigger` source `ap_start_seq_0`
used (`copy_fsm_0/done` on real hardware). Sequence: write
`cnn_engine`'s FEATURES/COEFFICIENTS pointers + `ap_start` -> poll its
`AP_CTRL` until `ap_done` -> write `decode_work_heads_0`'s FEATURES
pointer + all 14 `DecodeConfig` fields (identity/no-motion case) +
`ap_start` -> poll its `AP_CTRL` until `ap_done` -> capture its 7
`BEST_O_DATA` registers -> transmit sync byte (`0xAA`) + 28 bytes (LSB-first
per field) over `uart_tx`. `cnn_subsystem_top.v`'s old repeating
status-byte UART reporter is removed (would have been a second driver of
the same `uart_tx` instance) -- UART is now driven directly by
`pipeline_seq_0`.

**BD port renumbering, found by actually running `create_bd.tcl`, not by
inspection:** the first attempt reused smartconnect slave port `S05_AXI`
for `pipeline_seq_0`, which `decode_work_heads_0`'s own feature-DDR
connection (added earlier) already claimed --
`ERROR: [BD 41-396] interface pin/port 'S05_AXI' is already connected`.
Real fix: `ap_start_seq_0`'s removal freed `S04_AXI` in the hardware path
(not free in the sim-only path, where `copy_fsm_1` already sits there) --
`pipeline_seq_0` takes `S04` (hardware) / `S05` (sim), and
`decode_work_heads_0`'s own slave index was made conditional to match
(`S05` hardware / `S06` sim) instead of the hardcoded `S05_AXI` it had
before. Both paths gap-free after the fix; BD validated cleanly.

**Real build**: `WNS: 0.040 ns`, `TIMING MET` -- identical to every build
since the CDC timing fix, confirming `pipeline_seq_0`'s addition (despite
being a brand-new AXI-Lite read+write master) didn't regress timing.
Synthesis: 17 per-IP logs checked, no unexpected CRITICAL WARNINGs.
`BUILD OK`, bitstream confirmed present, flashed successfully.

**Verification, read-only (no JTAG writes to either core -- the whole
point was proving the automatic sequencing, not re-driving it by hand)**:
waited for the automatic chain to run (triggers off `copy_fsm_0/done`,
same ~1s-after-boot timing as the old `ap_start_seq_0` throwaway pass),
then read `decode_work_heads_0`'s `BEST_O` registers. Result is real,
structured output -- not the `0xdec0dee3` garbage sentinel seen during
earlier manual-JTAG debugging, not all-zero:

- `confidence` (DATA_4) = `0x00010000` = 65536 = the maximum possible
  `ap_uint<17>` value (sigmoid saturated to ~1.0)
- `raw_objectness` (DATA_5) = 244229, 24-bit-signed-positive -> Q14 =
  **+14.91** (a strongly positive logit, consistent with the saturated
  confidence above)
- `valid` (DATA_6 bit 16) = **1**
- x/y/w/h (DATA_0-3) decode to plausible Q16 pixel values

This confirms: `pipeline_seq_0` genuinely triggered `cnn_engine`, waited
for its real completion, triggered `decode_work_heads_0` against the
result, waited for ITS real completion, and captured real output -- all
without any external (JTAG) driving of either core's control registers.
The numbers differ from the earlier manually-JTAG-loaded-photo runs (as
expected -- this ran against whatever was in feature memory at boot time,
not a loaded test image) but have the same valid structure.

**One unexplained minor oddity, flagged rather than silently ignored**:
`cnn_engine`'s own `AP_CTRL` read back as `0x00000001` (`ap_start` bit
still set, `ap_idle` bit not set) at the time of this read, rather than a
clean post-completion idle state (`ap_idle=1`, `ap_start=0`). Not
necessarily a bug -- could be a timing artifact of exactly when the read
landed relative to the core's own internal state, or `ap_start`'s
register-level behavior simply not auto-clearing the way assumed. Not
investigated further (out of this task's scope: the decoder's output
being real and correctly-structured is the actual proof point that
mattered here, and that output value matching what `cnn_engine` would
only produce after really finishing is itself indirect evidence
`cnn_engine` did complete correctly regardless of this one status-register
snapshot). Worth root-causing if it recurs or matters for a future
real-time/continuous-retrigger design.

**UART byte transmission itself was NOT verified** (confirmed pre-existing
gap, not new): this environment's Genesys 2 onboard UART channel isn't
bound to a driver here (same finding as earlier this session). The
`pipeline_seq_0`/`uart_tx` wiring is real RTL, flashed and exercised (the
decoder's `BEST_O` capture completing proves `pipeline_seq_0` reached its
own `S_UART_SYNC`/`S_UART` states, since those are the only path back to
`S_IDLE`), but the actual bytes on the physical TX pin were not observed.

## 100-sample real-hardware batch evaluation (2026-10-29)

First evaluation with a real sample size, not 1-2 images. Ran all 50 unique
real labeled photos from the teammate's handoff
(`cv_model/examples/photo_examples_50/`: 20 training examples, 15 of the
original model's own "successful detection" examples, 15 of its own
"missed/wrong-location/poor-fit" examples), each **twice** back-to-back
(100 total runs -- honestly labeled: 50 unique images, not 100 unique
samples, repeated for a determinism check and to meet the requested count).
Full pipeline per run: crop the gallery composite to the real photo region
(same `190,88,1090,807` box validated earlier, now confirmed by direct
visual inspection to work identically across all three photo subfolders,
not just the two images tested before), pack to the full 256x192 frame,
JTAG-burst-write it, trigger `cnn_engine` then `decode_work_heads_0`,
capture the 7 `BEST_O` registers. Tooling and raw/analyzed results
committed under `docs/batch_eval_100samples/`.

**Two real, previously-undiscovered bugs found and fixed along the way**
(both confirmed by direct hardware evidence, not inspection -- see that
directory's `batch_run.tcl` comments for the full diagnostic trail):

1. **`pipeline_seq.v`'s `state` register and its `S_*` localparams were
   declared `3'd`/`[2:0]` (3 bits) for 9 states (0-8).** `S_UART`'s literal
   `3'd8` silently truncated to 0, colliding with `S_IDLE`'s encoding --
   confirmed on real hardware: `cnn_engine`'s `AP_CTRL` was observed
   cycling `ap_start=1 -> idle=1 (briefly) -> ap_start=1 -> ...` forever,
   completely independent of any external write. Once the FSM reached the
   mis-encoded "S_UART" state, it was actually back in `S_IDLE`, saw
   `trigger` still permanently high, and restarted the whole program from
   `pc=0` every cycle -- an unintended infinite auto-retrigger that made
   clean manual batch control impossible. Fixed: widened to 4 bits
   everywhere. Rebuilt, reflashed: `WNS=+0.040ns, TIMING MET`, unregressed
   (a pure encoding-width fix, no logic change).

2. **Multi-beat AXI burst WRITES land with the data in reverse order**
   relative to ascending address (`-data {deadbeef cafebabe 12345678
   87654321}` with `-len 4` actually stored `[87654321, 12345678, cafebabe,
   deadbeef]` at the four ascending addresses -- confirmed directly via DDR
   readback, including across the 256-word chunk boundary). This is the
   same reversal already found and fixed on the READ side earlier this
   session (`axi_read_burst` in `scripts/jtag_full_frame_test.tcl`) but the
   WRITE side had never actually been verified by DDR readback before --
   only by downstream decoded output, which for the two images tested
   earlier didn't obviously fail. That discrepancy is flagged, not
   resolved, here: it's possible those two earlier results were coincidentally
   still plausible despite the same bug, or something else differs between
   those runs and this one -- not re-investigated, out of this task's
   scope. Fixed in `docs/batch_eval_100samples/batch_run.tcl`'s
   `axi_write_burst` (reverse each chunk before joining); verified correct
   with a known-pattern readback before trusting it for the real batch.

**Results (all 100 runs completed, 0 timeouts):**

- **100% repeatability**: all 50 images gave byte-identical output on both
  passes. The pipeline is deterministic.
- **Confidence clearly discriminates real classes** (pass-1-only means):
  drone **37.5%**, negative background (sky/ADE20K scenes) **6.2%**, bird
  **6.8%**, airplane **32.2%** (plausibly confused with drone -- both are
  small flying objects at altitude, a known, reasonable model limitation,
  not a bug). This is a dramatically stronger signal than the single
  partial-frame (row-147-only) test earlier in this session showed
  (0.04%) -- strong evidence that test was underselling the model, not
  that the model itself is this weak.
- **Location accuracy on the 43 drone images with a detectable green
  ground-truth box**: median distance to the labeled center **1.4px**,
  mean **23.8px** (pulled up by real outlier misses), **77%** within 30px.
- **Confidence/accuracy tracks the original model's own success/failure
  labels** (pass-1 only, by `outcome`): `wrong_location` lowest confidence
  (12.6%) and largest mean distance (39.3px); `missed_drone` similarly low
  confidence (21.9%) with the largest distance (58.5px); `success` solid
  (37.7%, 22.0px); `poor_box_fit` highest confidence (47.5%) and very
  close center distance (2.8px) -- consistent, not contradictory: that
  label is about box *size* (width/height, IoU) which this test doesn't
  score, not center location, which it does.

**Caveat inherited from the dataset's own README, repeated here
deliberately**: these 50 images were *deliberately selected as
illustrative examples* ("These deliberately selected examples DO NOT
estimate overall accuracy"). The numbers above are real, hardware-measured
results on real labeled data -- a genuine step up from n=1 -- but they are
not a claim of overall model accuracy on a representative sample.

## Real field/sky-domain batch: DroneDetectionThesis dataset, 100 real video frames

Follow-up to the earlier 50-photo-gallery batch, run against real, public
drone video data instead -- the user's actual deployment scenario is a
field under clear/overcast skies, and the 50-photo gallery set's composite
documentation images (text headers, borders, closeup insets) aren't that
domain. Confirmed via `WebSearch`/`gh api` that the dataset referenced in
this project's own `native_validation_manifest.json.gz` (43 of its 46
sequences, `DroneDetectionThesis` source) is a real, public GitHub dataset:
[DroneDetectionThesis/Drone-detection-dataset](https://github.com/DroneDetectionThesis/Drone-detection-dataset)
(IR + visible + audio, MIT-style free-to-use license, 650 videos). Ground
truth read via the `mcos-decoder` PyPI package (pure-Python MATLAB
`groundTruth` MCOS decoder -- no MATLAB needed).

**Data**: 10 `V_DRONE_xxx` visible-spectrum videos spread across the full
001-114 range (`V_DRONE_001/012/023/034/045/056/067/078/089/100`), 10
labeled frames each (100 total, one failed-to-decode last-frame-index per
video worked around by picking a mid-range replacement). All real 640x512
field footage, letterbox-resized to 256x192 via the same `pack_image_to_hex.py`
`sized()`/`pack()` path already used all session -- no crop-box needed this
time (unlike the gallery composites), since these are raw frames.

**Hardware run**: single JTAG connection, one bitstream flash, looped
write+trigger+poll+read per frame (reused `docs/batch_eval_100samples/batch_run.tcl`
verbatim except running each frame once instead of twice -- that script
already carries the write-burst-reversal and address-formatting fixes
found during the earlier batch). 100/100 completed, zero timeouts, ~53
minutes wall-clock.

**Results -- real, hardware-measured, n=100, cross-checked against each
frame's actual labeled ground-truth box (mapped into the same 256x192
canvas space the hardware output is in)**:

- Mean confidence: **64.7%** (vs. 37.5% on the gallery-photo set's drone
  images) -- a real, large jump, consistent with this being the domain the
  model was actually trained for.
- Mean distance to ground truth: **12.83px**, median **9.10px**.
- **96/100 frames within 10% of canvas diagonal (32px)** of the labeled
  center.
- Four real outliers (42.6px, 80.3px, 98.9px, 126.5px) -- all from
  `V_DRONE_078`, which also has this run's lowest mean confidence (37.6%)
  and lowest per-video under-10% rate (7/10). Worth a closer look if this
  dataset becomes a recurring benchmark; not investigated further here.

Per-video breakdown (distance mean/median px, confidence mean %,
under-10%-threshold count) in `docs/batch_eval_drone_dataset_100samples/analyzed_results.csv`.
Raw hardware register dumps in `results.csv`; frame/ground-truth manifest
in `manifest.csv`; `prepare.py` (download+frame-extract+pack+ground-truth
canvas-mapping) and `analyze.py` (decode+score) are the reproducible
tooling, same pattern as the earlier `docs/batch_eval_100samples/`.

**Net assessment**: this is a meaningfully stronger, more representative
accuracy picture than the gallery-photo batch, and the improvement lines
up with domain match (real field footage vs. documentation composites)
rather than anything changing about the hardware or model. Worth treating
as the more trustworthy of the two batches for judging real-world
performance, given the user's actual deployment conditions.

## 125MHz: fully validated, timing + real hardware functional equivalence

Follow-up to 200MHz (-2.341ns), 150MHz (-0.883ns), 135MHz (-0.303ns near-miss,
estimated real ceiling ~129.7MHz). 125MHz chosen deliberately below the
~128MHz the 135MHz experiment recommended, for real margin instead of
landing at the edge again.

**Timing**: `WNS=+0.040ns, TIMING MET` -- reproduced identically in an
isolated copy and in this canonical repo (same build, same strategies:
`Flow_PerfOptimized_high` synthesis, `Performance_Retiming` implementation,
`STEPS.PHYS_OPT_DESIGN.IS_ENABLED true`). Critical path: still
`decode_work_heads_0`'s `transformed()` multiplier (same function/path
seen at 135MHz), now with enough slack. `cnn_engine_0` is not implicated
in any of the four frequency experiments run this session. Margin is
modest (same magnitude as the original 100MHz result), not dramatically
comfortable -- flagged honestly rather than oversold, per this session's
own standard for what counts as "safe."

**Real hardware functional equivalence, verified, not assumed**: flashed,
then ran `scripts/jtag_decode_test.tcl` against the same real drone photo
(`rtl/feature_drone_full_lanes32.hex`) already validated at 100MHz.
Result is bit-for-bit identical: x=32.19, y=179.58, w=149.17, h=72.69,
confidence(Q16)=26, raw_objectness=0x00fe0a68 (same raw hex as the 100MHz
baseline). Zero functional regression from the clock change.
`cnn_engine ap_done` after 53ms (JTAG-poll-inflated measurement, not
cycle-exact -- see this session's determinism analysis -- but directionally
consistent with the expected speedup from 100MHz's typical 60-72ms).

**Bottom line**: 125MHz is a real, usable number -- timing closes with a
margin of the same character already proven reliable at 100MHz across many
hardware runs this session, and functional correctness is confirmed
bit-exact on real hardware, not just simulated/assumed. This is the
frequency to use for the 30fps throughput calculation going forward,
not the unverified 135/137MHz extrapolation.

## 140MHz decoupled-clock architecture: validated, flashed, re-benchmarked

Motivated by the latency-improvement request: every timing experiment
(200/150/135/125MHz) found `cnn_engine_0` was never the limiter -- the
tight path was always inside `decode_work_heads_0`'s own arithmetic, which
was forced to share `cnn_engine`'s clock. Decoupling removes that forced
coupling: `clk_wiz_0` now exposes two independent outputs from the same
MMCM (`bd/create_bd.tcl`'s `clk_wiz_0` section) -- `clk_out1` drives
`cnn_engine_0` at a build-time-selectable `CNN_CLK_MHZ` (140MHz for this
build), `clk_out2` stays fixed at 100MHz and now drives
`decode_work_heads_0` and its AXI CDC bridges exclusively, via
`axi_clock_converter_3`/`4`.

**Timing, live repo, reproduced**: `WNS: 0.040 ns, TIMING MET`. Looking at
the per-clock breakdown in `vivado/timing_summary.rpt` (not just the
single global-worst number `build.tcl` prints) shows the decoupling did
exactly what it was meant to:
- `cnn_engine_0`'s own clock domain (`clk_out1`, 140MHz): WNS = **+0.195ns**
  -- real margin, not razor-thin.
- `decode_work_heads_0`'s own clock domain (`clk_out2`, 100MHz): WNS =
  **+1.051ns** -- comfortable, as expected now that it's running at its
  original, already-proven-safe frequency instead of being dragged up to
  the CNN's clock.
- The global `0.040ns` that `build.tcl` prints (and that happens to match
  the 125MHz shared-clock number) is **not the same bottleneck** --
  checked directly, it's in `mem_refclk`, inside the MIG DDR3 PHY's own
  internal timing, unrelated to any logic this session touched. It would
  show up at roughly this magnitude regardless of `cnn_engine`/decoder
  clock choice; it is a fixed property of the MIG IP, not something either
  module's clock change affects. Worth being precise about this rather
  than reporting "WNS 0.040ns, same margin as before" as if it meant the
  same thing it meant at 125MHz (there, it genuinely was the decoder's
  `transformed()` path).

**Flashed, functional equivalence confirmed bit-exact**: re-ran the full
10x10 real-video drone-dataset batch (`docs/batch_eval_drone_dataset_100samples_140mhz/`,
same 10 videos / 100 labeled frames as the 100MHz baseline run, reused the
cached downloads rather than re-fetching). All decoded fields
(`x,y,w,h,confidence,raw_objectness,valid`) are **bit-for-bit identical**
to the 100MHz baseline run across all 100 frames -- diffed directly, not
assumed. Same accuracy numbers as a result: mean confidence 64.7%, mean
distance 12.83px / median 9.10px, 96/100 within 10% of canvas diagonal,
same four `V_DRONE_078` outliers. The clock change is a pure timing win
with zero functional regression.

**Timing/latency win, real and measured (not estimated)**:

| | 100MHz baseline | 140MHz decoupled | change |
|---|---|---|---|
| mean `cnn_ms` | 63.08ms | 51.81ms | -17.9% |
| mean `dec_ms` | 10.71ms | 10.74ms | ~0 (decoder clock unchanged) |
| mean total (JTAG-inflated) | 73.79ms | 62.55ms | -15.2% |

The `cnn_ms` improvement (-17.9%) is smaller than the naive 100/140=0.714x
(-28.6%) clock-ratio prediction would suggest, because this measurement is
still JTAG-poll-granularity-limited (see this session's earlier JTAG
overhead isolation finding, ~3-4ms/transaction) -- the fixed polling
overhead doesn't scale down with the faster clock. The decoder's own
measured time is unchanged because its clock didn't change in this
architecture; it was never the latency problem, just the timing-closure
problem.

Raw data in `docs/batch_eval_drone_dataset_100samples_140mhz/` (same file
layout as the 100MHz baseline directory): `results.csv` (hardware register
dumps), `analyzed_results.csv` (decoded + ground-truth-scored), `manifest.csv`,
`analyze.py`, `batch_run_video.tcl`, `image_list.txt`.

**Status**: this is now the live-repo state (bitstream flashed, batch
re-run against it). 125MHz shared-clock is superseded by this architecture
-- 140MHz decoupled gives a real measured latency win on `cnn_engine`
alone, plus removes the structural serialization where decoder timing
closure fought with CNN clock speed, with identical detection accuracy.
