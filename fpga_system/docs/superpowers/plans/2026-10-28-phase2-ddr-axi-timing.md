# Phase 2: Standalone CNN-core + DDR3/MIG + AXI timing subsystem Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a standalone Genesys 2 Vivado project (no camera) that routes the
regenerated CNN core against real DDR3/MIG + AXI interconnect, loads trained
coefficients into DDR via an on-chip BRAM staging buffer, and produces a real
post-route timing number for this subsystem alone.

**Architecture:** Vivado IP-Integrator block design: `mig_7series` (Genesys2 `H`
board preset, DDR3) <-> `smartconnect` (width conversion + multi-master
arbitration) <-> three AXI masters: the regenerated `cnn_engine` core's two
HLS-generated AXI-M ports (`m_axi_feature_ddr`, `m_axi_coefficient_ddr`), a new
`coeff_bram_stage` + `copy_fsm` master that burns coefficients from an on-chip
BRAM (`$readmemh` of `coefficients.hex`) into the DDR3 coefficient region once
after `init_calib_complete`, and a `jtag_axi` master kept permanently as a debug
backdoor (per SESSION_HANDOFF_20261028.md). `cnn_engine`'s AXI-Lite control port
is also driven from `jtag_axi` so `ap_start`/`ap_done` can be poked from Tcl
without a camera or software stack. `ap_clk` is tied directly to MIG's `ui_clk`
to avoid a CDC in this standalone phase; multi-clock-domain integration with the
camera's pixel clock is explicitly out of scope here (handoff phase 3+).

**Tech Stack:** Vivado/Vitis 2023.2, `xc7k325tffg900-2`, board part
`digilentinc.com:genesys2:part0` (board files already confirmed present at
`~/fpga/vivado-boards/new/board_files/genesys2/H`), IP: `mig_7series_v4_2`,
`smartconnect_v1_0`, `jtag_axi_v1_2` (all confirmed present in the 2023.2
catalog). xsim for functional checks, Tcl batch mode for everything else,
per `vivado-build-and-flash` skill conventions (never pipe long runs through
`tail`/`head`; always `tee` to a log; watchdog every testbench).

**Spec:** `~/fpga/SESSION_HANDOFF_20261028.md` (CV/CNN integration section,
"Remaining phases" item 2) and `~/fpga/genesys2-cv-model/PHASE1_STATUS.md`
(what Phase 1 already proved). Interface contract pulled from
`~/Downloads/Genesys2_Teammate_Handoff_20261028.zip:cv_model/fpga/README.md`
and `cv_model/fpga/cnn_hls/program.h`.

## Global Constraints

- Part: `xc7k325tffg900-2`. Board preset: Genesys2 `H` (`mig.prj` already
  validated for `DDR3_SDRAM/Components/MT41J256M16XX-107`, differential sys
  clock, active-low reset, 200.02 MHz input clock).
- `cnn_engine`'s feature-memory AXI-M port (`m_axi_feature_ddr_*`) is 256
  bits wide; its coefficient AXI-M port (`m_axi_coefficient_ddr_*`) is 128
  bits wide; its control port is AXI-Lite (`s_axi_control`). Exact port list:
  `~/fpga/genesys2-cv-model/cnn_rtl_sim_work/cnn_engine.v`.
- Feature memory allocation: `FEATURE_WORDS=73728` (256-bit words = 2,359,296
  bytes). Coefficient allocation: `COEFFICIENT_WORDS=41600` (128-bit words =
  665,600 bytes). Input pixel data is NOT a separate DDR region — it lives
  inside the feature-memory array at word offset `INPUT_WORDS`-complementary
  offset 49152 (op 0 in `PROGRAM[]` reads `{6,0,0,49152,...}`, i.e. writes to
  feature-word offset 0, input occupies words 0..49151 = bytes
  0..1,572,863). All three `input_*.bin` files are exactly 1,572,864 bytes,
  confirming this. Never allocate a separate "input" DDR region — it is a
  sub-range of the feature region.
- `coefficients.hex` already exists at
  `~/fpga/genesys2-cv-model/cnn_rtl_sim_work/coefficients.hex`: exactly 41,600
  lines, one 128-bit hex word per line, already in the exact word order
  `cnn_engine` expects (proven byte-identical in Phase 1's RTL sim). Reuse it
  verbatim for `$readmemh` — do not regenerate it from `coefficients.bin`.
- `~/fpga/genesys2-cv-model` is not a git repo yet. Task 1 initializes one.
  `vivado/` (generated project) and `.venv/` are gitignored, matching
  `~/fpga/genesys2-ov5640-hdmi` convention.
- Camera RTL is explicitly out of scope — this subsystem never instantiates
  `cam_capture`/`hdmi_out`/etc. Keep it that way so this build's timing number
  isolates the new DDR/AXI risk from the already-proven camera risk.
- Source regenerated RTL from `~/fpga/genesys2-cv-model/cnn_rtl_sim_work/`
  (Phase 1's byte-identical output), not from the teammate's original
  `cnn_routed_core/` checkpoint — Phase 1 established the regenerated core is
  the one to build on.

## Review Focus

- **MIG calibration in simulation never finishes / times out.** `mig_7series`
  behavioral simulation of DDR3 calibration is notoriously slow. Task 4's
  testbench must use MIG's simulation-speedup generic
  (`SIM_BYPASS_INIT_CAL = "FAST"`, exposed by the IP) and still carry an
  explicit watchdog, or calibration alone can run for simulated minutes with
  zero output and look identical to a real hang.
- **Coefficient endianness/word-packing mismatch is silent.** Phase 1's own
  documented gotcha: a missing/misordered ROM value "silently produced a
  false-positive pass... core effectively did nothing." Task 3's testbench
  must assert the DDR contents word-for-word against `coefficients.hex`
  after the copy FSM completes, not just check `copy_done` went high.
- **AXI ID width / burst-length mismatch between the HLS-generated master
  ports and SmartConnect's auto-negotiated widths.** `cnn_engine`'s AXI
  masters were generated by Vitis HLS with specific ID widths; SmartConnect
  auto-sizing can silently widen/narrow IDs. Task 2's `validate_bd_design`
  step must be checked for width-mismatch warnings, not just "no errors."
- **DDR address-map collisions between the three masters' regions.** The
  feature region (0..2,359,295), coefficient region, and the copy FSM's
  target range must be assigned via `assign_bd_address` to non-overlapping
  offsets — report and eyeball `report_bd_address_map` in Task 2, don't
  assume the wizard's defaults are disjoint.
- **Clock domain assumption (`ap_clk` = MIG `ui_clk`) breaks a later phase
  silently if not documented.** Task 4 must state explicitly in the top
  wrapper's header comment that this ties `ap_clk` to `ui_clk` and that
  camera integration (handoff phase 3) will need a real CDC — so a future
  session doesn't rediscover this the hard way mid-route.

---

## Task 1: Project scaffold, git init, and MIG-only block design

**Files:**
- Create: `~/fpga/genesys2-cv-model/.gitignore`
- Create: `~/fpga/genesys2-cv-model/scripts/create_project.tcl`
- Create: `~/fpga/genesys2-cv-model/bd/create_bd.tcl`
- Create: `~/fpga/genesys2-cv-model/docs/PHASE2_LOG.md`

**Interfaces:**
- Produces: a Vivado project at `vivado/genesys2_cv.xpr`, top-level block
  design `cv_subsystem` (empty except `mig_7series_0`) instantiable by Task 2.

- [ ] **Step 1: `git init` in `~/fpga/genesys2-cv-model`, commit the existing
  Phase 1 artifacts (`PHASE1_STATUS.md`, `cnn_hls_work/`, `cnn_rtl_sim_work/`
  minus simulator scratch) as the baseline commit.**

- [ ] **Step 2: Write `.gitignore`** excluding `vivado/`, `.venv/`,
  `*.jou`, `*.log`, `*.pb`, `xsim.dir/`, `.Xil/`.

- [ ] **Step 3: Write `scripts/create_project.tcl`** — `create_project` with
  `-part xc7k325tffg900-2 -board_part digilentinc.com:genesys2:part0:<rev>`
  (query `get_board_parts -filter {NAME =~ "*genesys2*"}` for the exact
  string once the board files are on the part repo path). No RTL sources
  added yet; this task is block-design-only.

- [ ] **Step 4: Write `bd/create_bd.tcl`** — `create_bd_design cv_subsystem`,
  `create_bd_cell -type ip -vlnv xilinx.com:ip:mig_7series:4.2 mig_7series_0`,
  apply the Genesys2 `H` board preset to it (`set_property CONFIG.XML_INPUT_FILE
  {mig_b.prj}` pointed at the board's `mig.prj`, per the board-preset flow),
  leave its AXI/UI ports unconnected for now. Run
  `vivado -mode batch -source scripts/create_project.tcl -source bd/create_bd.tcl`,
  tee to `docs/PHASE2_LOG.md`.

- [ ] **Step 5: Verify** — `validate_bd_design` on `cv_subsystem` reports no
  errors; MIG's "Generate Output Products" step in the log shows the DDR3
  pin-out matching the Genesys2 board file (spot check against
  `~/fpga/vivado-boards/new/board_files/genesys2/H/part0_pins.xml`).

- [ ] **Step 6: Commit** `scripts/create_project.tcl`, `bd/create_bd.tcl`,
  `.gitignore`, `docs/PHASE2_LOG.md`.

## Task 2: Wire the CNN core into the block design

**Files:**
- Create: `~/fpga/genesys2-cv-model/rtl/cnn_core/` (copy of all
  `cnn_engine*.v` + `*_ROM_AUTO_1R.v`/`.dat` files from `cnn_rtl_sim_work/`)
- Modify: `~/fpga/genesys2-cv-model/bd/create_bd.tcl`

**Interfaces:**
- Consumes: `mig_7series_0`'s AXI slave port and `ui_clk`/`ui_clk_sync_rst`/
  `init_calib_complete` from Task 1.
- Produces: `cnn_engine_0`'s three AXI ports connected through a
  `smartconnect_0` to MIG; `jtag_axi_0` added as a fourth-port debug master,
  also wired to `cnn_engine_0/s_axi_control`. `report_bd_address_map` output
  saved to `docs/PHASE2_LOG.md` for Task 3/4 to extend.

- [ ] **Step 1: Copy RTL** — `rtl/cnn_core/` gets every `.v`/`.dat` file
  `cnn_rtl_sim_work/` used in Phase 1's sim (the full generated hierarchy
  under `cnn_engine.v`), so the block design references files under version
  control instead of the scratch sim directory.

- [ ] **Step 2: Extend `bd/create_bd.tcl`** — add `smartconnect_0` (3 slave
  AXI, 1 master AXI toward MIG's AXI slave; the width conversion from
  `cnn_engine`'s 128-bit coefficient port and MIG's native port width is
  SmartConnect's job, no manual width logic needed), add `cnn_engine_0` as an
  RTL-module BD cell (`create_bd_cell -type module`, referencing
  `rtl/cnn_core/cnn_engine.v` after `add_files`), add `jtag_axi_0`. Connect
  `cnn_engine_0.ap_clk`/`ap_rst_n` to MIG's `ui_clk`/`ui_clk_sync_rst` (see
  Global Constraints — document this tie in a comment at the top of the
  script). Use Vivado's connection automation
  (`apply_bd_automation -rule xilinx.com:bd_rule:axi4`) for the AXI legs,
  then `assign_bd_address` for all address spaces.

- [ ] **Step 3: Verify** — `validate_bd_design` clean; grep the log for
  `WARNING.*width` and resolve any ID/data-width mismatch Vivado flags
  (Review Focus item 3) rather than dismissing it; `report_bd_address_map`
  shows the feature region, coefficient region, and `jtag_axi_0`'s access
  window as non-overlapping (Review Focus item 4).

- [ ] **Step 4: Commit** `rtl/cnn_core/`, updated `bd/create_bd.tcl`,
  address-map report.

## Task 3: Coefficient BRAM staging + copy FSM, simulated standalone

**Files:**
- Create: `~/fpga/genesys2-cv-model/rtl/coeff_bram_stage.v`
- Create: `~/fpga/genesys2-cv-model/rtl/copy_fsm.v`
- Create: `~/fpga/genesys2-cv-model/sim/tb_bram_to_ddr.v`
- Create: `~/fpga/genesys2-cv-model/sim/axi_ram.sv` (copy of
  `cnn_rtl_sim_work/axi_ram.sv`, reused as the behavioral DDR stand-in so
  this testbench runs without MIG's slow calibration model)

**Interfaces:**
- Consumes: none from earlier tasks (this is a standalone AXI master +
  behavioral-slave testbench; it joins the real block design in Task 4).
- Produces: `copy_fsm` module with ports
  `(input clk, input rst_n, input start, output done, <AXI-M master ports
  matching cnn_engine's m_axi_coefficient_ddr_* naming/width convention>)` —
  Task 4 instantiates this exact port list as the BD's fourth AXI master.

- [ ] **Step 1: Write `coeff_bram_stage.v`** — a 41,600 x 128-bit BRAM,
  `$readmemh("coefficients.hex", mem)` at the relative path
  `../cnn_rtl_sim_work/coefficients.hex` (or copy the hex file alongside the
  RTL — implementer's choice, document whichever is picked), simple
  synchronous read port.

- [ ] **Step 2: Write `copy_fsm.v`** — on `start`, bursts all 41,600 words
  from `coeff_bram_stage` out over a 128-bit AXI-M write channel to a
  parameterized base address (the coefficient region's DDR offset from
  Task 2's address map), asserts `done` after the last `BVALID`/`BRESP` OKAY.

- [ ] **Step 3: Write `tb_bram_to_ddr.v`** — instantiates `copy_fsm` +
  `coeff_bram_stage` against `axi_ram.sv` (sized to at least the coefficient
  region's byte range), pulses `start`, waits for `done` with a `#2_000_000`
  watchdog (per `vivado-build-and-flash` skill convention), then loops over
  all 41,600 words comparing `axi_ram`'s contents against
  `coefficients.hex` read via `$readmemh` into a reference array, incrementing
  an `errors` counter and `$display`-ing any mismatch with its word index
  (Review Focus item 2 — assert content, not just `done`).

- [ ] **Step 4: Run** `xvlog`+`xelab`+`xsim` (or extend `sim.sh`), teed to a
  log, with the watchdog in place. Expected: `errors == 0` printed before
  `$finish`.

- [ ] **Step 5: Commit** `rtl/coeff_bram_stage.v`, `rtl/copy_fsm.v`,
  `sim/tb_bram_to_ddr.v`, `sim/axi_ram.sv`, sim log.

## Task 4: Full standalone top-level, MIG-calibration-aware simulation

**Files:**
- Create: `~/fpga/genesys2-cv-model/rtl/cnn_subsystem_top.v`
- Create: `~/fpga/genesys2-cv-model/sim/tb_cnn_subsystem_top.v`
- Modify: `~/fpga/genesys2-cv-model/bd/create_bd.tcl` (add `copy_fsm`/
  `coeff_bram_stage` as the block design's fourth AXI master, per Task 3's
  Interfaces)

**Interfaces:**
- Consumes: `copy_fsm`'s exact port list from Task 3; the block design from
  Task 2 (now with 4 AXI masters into `smartconnect_0`).
- Produces: `cnn_subsystem_top` — ports `(sys_clk_p, sys_clk_n, sys_rst,
  ddr3_* per Genesys2 XDC, uart_tx)`. Reports status (calib complete /
  copy done / `ap_done`) over UART, reusing the `uart_tx.v` module pattern
  from `~/fpga/genesys2-ov5640-hdmi/rtl/uart_tx.v`.

- [ ] **Step 1: Extend `bd/create_bd.tcl`** to add `copy_fsm_0` +
  `coeff_bram_stage_0` as BD cells, wire `copy_fsm_0`'s AXI-M into
  `smartconnect_0`'s fourth slave port, trigger `start` from
  `mig_7series_0.init_calib_complete` (rising edge). Re-run
  `validate_bd_design`.

- [ ] **Step 2: Write `cnn_subsystem_top.v`** instantiating the block design
  (`cv_subsystem_wrapper`), the Genesys2 differential `sys_clk`, and a
  minimal UART status reporter (status bits: `init_calib_complete`,
  `copy_fsm_done`, `cnn_engine_ap_done`) — module header comment states the
  `ap_clk = ui_clk` tie explicitly (Review Focus item 5).

- [ ] **Step 3: Write `sim/tb_cnn_subsystem_top.v`** — instantiates
  `cnn_subsystem_top` against MIG's provided Verilog behavioral/UNISIM model
  with `SIM_BYPASS_INIT_CAL = "FAST"` set on the MIG BD cell (via
  `set_property CONFIG.SIM_BYPASS_INIT_CAL FAST` on `mig_7series_0`,
  simulation-only — must NOT be left set for the Task 5 hardware build),
  drives `sys_rst`, waits for `init_calib_complete` then `copy_fsm_done`
  then `cnn_engine_ap_done`, each gated by its own watchdog
  (`#2_000_000` per stage per the skill convention), `$display`s which stage
  it reached if any watchdog fires.

- [ ] **Step 4: Run the simulation**, teed to a log. Expected: all three
  status signals assert in order, no watchdog fires.

- [ ] **Step 5: Commit** `rtl/cnn_subsystem_top.v`, `sim/tb_cnn_subsystem_top.v`,
  updated `bd/create_bd.tcl`, sim log.

## Task 5: Synthesis, implementation, and the real timing number

**Files:**
- Create: `~/fpga/genesys2-cv-model/constraints/genesys2_cv.xdc`
- Create: `~/fpga/genesys2-cv-model/scripts/build.tcl`
- Create: `~/fpga/genesys2-cv-model/PHASE2_STATUS.md`

**Interfaces:**
- Consumes: `cnn_subsystem_top` from Task 4.
- Produces: `PHASE2_STATUS.md` — the artifact the next session (or the full
  system-integration phase) reads, mirroring `PHASE1_STATUS.md`'s format.

- [ ] **Step 1: Write `constraints/genesys2_cv.xdc`** — `sys_clk_p/n`
  differential pins and `IOSTANDARD`/package pins pulled from
  `~/fpga/vivado-boards/new/board_files/genesys2/H/part0_pins.xml` for the
  200 MHz oscillator and the DDR3 bank (MIG's own output-product XDC,
  generated in Task 1, supplies the DDR3 signal pins — this file only needs
  the system clock/reset and UART pins that aren't MIG's).

- [ ] **Step 2: Write `scripts/build.tcl`** modeled on the
  `vivado-build-and-flash` skill's template — **make sure
  `SIM_BYPASS_INIT_CAL` is NOT set** on `mig_7series_0` for this run (Task 4's
  sim-only override must not leak into the hardware build). Runs
  synth_design + opt/place/route, prints `WNS: <n> ns` and `BUILD OK`.

- [ ] **Step 3: Run** `vivado -mode batch -source scripts/build.tcl 2>&1 |
  tee build.log` in the background (per skill guidance — this exceeds a
  foreground timeout). Grep for `CRITICAL`.

- [ ] **Step 4: Verify** — WNS is positive (or, if negative, that is itself
  the finding to report, not a failure to hide); utilization report shows
  total RAMB36 usage and compare against the handoff's ~249/445 estimate for
  CNN-core-plus-staging (no camera in this build, so the 72 RAMB36 camera
  estimate does not apply here).

- [ ] **Step 5: Write `PHASE2_STATUS.md`** — real WNS, real RAMB36/DSP/LUT
  utilization, any AXI width-mismatch or address-map findings carried over
  from Tasks 2-4's Review Focus items, and the same "what this means / next
  phase" structure `PHASE1_STATUS.md` used.

- [ ] **Step 6: Commit** `constraints/genesys2_cv.xdc`, `scripts/build.tcl`,
  `PHASE2_STATUS.md`, `build.log`.
