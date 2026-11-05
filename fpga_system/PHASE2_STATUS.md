# Phase 2: DDR3/MIG/AXI + coefficient loading — timing CLOSED, flashed and running on real hardware

**UPDATE (2026-10-29): timing is now MET (WNS=+0.040ns) and this design has
been flashed to a real Genesys 2 and run end-to-end over JTAG-AXI with real
photo data, producing data-dependent output in real (~60ms) time.** The
WNS=-1.954ns result and the "374-cycle" simulation finding documented below
are both historical -- the timing fix (a dedicated 100MHz clock domain for
`cnn_engine` via `clk_wiz`/`axi_clock_converter`, see `bd/create_bd.tcl`)
and the real-hardware verification that found the 374-cycle-style "instant
done" was actually a test-script bug (a stale read-to-clear `ap_done` bit,
not a hardware fault) are both in `docs/PHASE2_LOG.md`'s later sections.
Everything below this point is the original, now-superseded Task 1-5 record
-- left as-is for history, not current status.

---

Built the standalone CNN-core + DDR3/MIG + AXI interconnect + coefficient-loading
subsystem for the Genesys 2 (Kintex-7 XC7K325T), no camera, carried through
synthesis/place/route for a real post-route timing number. **This document
supersedes an earlier version of itself**: a code review caught that the
first build silently dissolved the entire coefficient staging BRAM array
down to nothing, which inflated this doc's original BRAM-headroom claim. The
numbers below are from a rebuilt, re-verified run with that bug (and four
smaller ones) fixed.

## Result: real post-route WNS, and the exact failing path (unchanged root cause)

```
WNS: -1.954 ns   (post-route)
TNS: -18774.691 ns, 41,553 of 238,301 endpoints failing (17.4%)
WHS:  0.028 ns   (hold is fine -- only setup fails)
```

Timing is **not met**. The worst path is the same one as the first build —
confirms the root cause is real, not an artifact of the bug since fixed:

```
Source:      cnn_engine_0/inst/grp_convolve_fu_357/.../shl_ln24_5_reg.../C
Destination: cnn_engine_0/inst/grp_convolve_fu_357/.../value_84_reg.../S
Clock:       clk_pll_i (MIG's internal PLL output -> ui_clk), period 4.444ns (225.02 MHz)
Data Path Delay: 5.994ns required vs 4.444ns available
Logic Levels: 33  (28x CARRY4, 1x LUT2, 3x LUT3, 1x LUT4)
```

Entirely inside `cnn_engine`'s own HLS-generated convolve logic, same class
of path as before (a long carry-chain accumulator). **Corrected Fmax
figure** (previous version of this doc derived this wrong, two ways — see
Fix 6 below): `cnn_engine` was HLS-synthesized for a 100 MHz target
(`rtl/cnn_core/cnn_engine.v:10`, `HLS_INPUT_CLOCK=10.000000`) and its own
Phase 1 out-of-context synthesis measured **128.12 MHz** Fmax
(`PHASE1_STATUS.md:26-27`). The real post-route slack gives an independent
floor: minimum period to close this specific path = 4.444 + 1.954 = 6.398ns
⇒ **156.3 MHz**, consistent with "well under 225 MHz" but above the
100 MHz the core was actually compiled for — Phase 1's own 128.12 MHz
estimate is the number to design the next clock domain around, not a
number derived from this one path's slack.

## BRAM: tighter than either estimate, not comfortable

```
Total: 358 RAMB36 + 13 RAMB18 ≈ 364.5 RAMB36-equivalent of 445 (~81.9%)
coeff_bram_stage_0 alone: 256 RAMB36 (41,600 x 128-bit, real data this time)
DSP: 274/840 (~32.6%)   LUT: 53,053/203,800 (~26.0%)   FF: 51,795/407,600 (~12.7%)
```

This is **higher than the handoff doc's own original ~249/445 (~72%)
estimate**, not lower — the opposite conclusion from this document's first
version, which was an artifact of the bug described below. There is very
little headroom left: the handoff's own Phase 3 camera-pipeline estimate
(~72 RAMB36) would put this design at ~436.5/445 (~98%) before Phase 4's
decoder is even considered. `coeff_bram_stage_0`'s 256 RAMB36 for 5,324,800
bits of real data is only ~56% packing efficiency (9,437,184 bits available)
-- a real, not-yet-attempted optimization opportunity (an explicit
`RAM_STYLE`/width-depth factorization) that could recover roughly 100
RAMB36 before Phase 3 needs the room.

## Fixes from a code review, applied and re-verified this session

A fresh-context review of Tasks 1-5 (full report in the git history) found
three Critical and several Important issues. Each below states what was
actually found, what was changed, and what evidence closes it -- per this
project's own standing rule, no fix is claimed without having watched it
work.

1. **(Critical) Coefficient staging BRAM silently dissolved to nothing.**
   `rtl/coeff_bram_stage.v`'s `HEXFILE` default was a path relative to the
   invoking directory; the per-IP out-of-context synthesis run's CWD is
   `vivado/*.runs/cv_subsystem_coeff_bram_stage_0_0_synth_1/`, where that
   path doesn't exist. `synth_design` treated the missing file as a
   non-fatal `CRITICAL WARNING` (`[Synth 8-4445]`) and dissolved the entire
   41,600x128 array into undriven registers -- 0 BRAM, 0 LUT in that IP's
   own report. The warning never reached `build.log` (it only exists in the
   per-IP `runme.log`), so the first build printed `BUILD OK` over it.
   **Fix:** `bd/create_bd.tcl` now sets `CONFIG.HEXFILE` to an absolute
   path. **Evidence:** this build's `utilization.rpt` shows
   `coeff_bram_stage_0` at 256 RAMB36 (quoted above), and the new per-IP
   `CRITICAL WARNING` sweep (fix 4) found nothing.
2. **(Critical) `cnn_engine`'s FEATURES/COEFFICIENTS base-address pointers
   were never programmed.** `rtl/ap_start_seq.v` wrote only `ap_start`;
   `cnn_engine`'s own AXI-M masters therefore addressed DDR offset 0x0,
   which the system address map decodes to `cnn_engine`'s *own control
   register segment*, not DDR. **Fix:** `ap_start_seq.v` now writes
   `ADDR_FEATURES_DATA_0/1` (0x10/0x14) and `ADDR_COEFFICIENTS_DATA_0/1`
   (0x1c/0x20) -- addresses confirmed by reading
   `rtl/cnn_core/cnn_engine_control_s_axi.v` directly, not assumed -- before
   `ADDR_AP_CTRL` (ap_start). **Evidence:** the write sequence is
   structurally correct (verified by re-reading the FSM); see finding 3 for
   what this did and did not resolve.
3. **(Critical, PARTIALLY addressed -- read this one carefully) the
   `cnn_ap_done` status bit is the same silent-false-positive class Phase 1
   documented, and is NOT resolved.** The first version of Task 4's
   testbench waited for `cnn_ap_done` with no lower bound on elapsed time --
   exactly the pattern `PHASE1_STATUS.md` itself warned about ("225 cycles,
   zero memory accesses, core effectively did nothing... always check cycle
   count... look like REAL work"). **What was fixed:** `sim/tb_cnn_subsystem_top.v`
   now asserts a 100,000-cycle floor between `copy_fsm_done` and
   `cnn_ap_done` (Phase 1's own real pass measured 3,774,628 cycles), and
   this check is **proven working**, not just present: re-running the
   simulation with fix 2 applied, it correctly **failed** --
   `cnn_ap_done` asserted after only **374 cycles**, averaging ~6.8 cycles
   per op across all 55 ops in `cnn_engine`'s program table. **What is NOT
   fixed:** that 374-cycle completion itself. Tracing `cnn_engine.v`'s own
   FSM, `ap_done` only sets when its internal program counter
   (`pc_fu_120`) reaches 55 -- and it is doing so far too fast, meaning the
   called `grp_convolve_fu_357`/`grp_vector_operation_fu_410` sub-blocks are
   themselves completing almost instantly. This is **not a Phase 2
   integration bug** (the AXI-Lite pointer-write sequence is structurally
   verified correct, and the previous paragraph's fix addressed the one gap
   that was found) -- it is something inside the HLS-generated core's own
   internal call/dispatch timing, and `rtl/cnn_core/*.v` is a frozen,
   Phase-1-validated artifact this phase does not modify. **This is now a
   tracked, open finding**, not a resolved one: before anyone relies on
   `ap_done`/the `interrupt` port meaning "the CNN actually finished a real
   pass" on this integration path, it needs a dedicated investigation --
   most likely comparing against Phase 1's own `cnn_rtl_sim_work` test
   harness using the identical AXI-Lite write sequence, or a waveform trace
   into the sub-blocks' own `ap_start`/`ap_ready`/`ap_done` handshake. This
   does not affect Task 5's timing-closure numbers above: Vivado times the
   synthesized logic regardless of what it computes at runtime.
4. **(Important) `build.tcl`'s own CRITICAL-WARNING check only grepped the
   top-level `build.log`**, which is exactly why finding 1 went unnoticed --
   the `[Synth 8-4445]` warning lived in a per-IP `runme.log` build.log
   never captures. **Fix:** `build.tcl` now sweeps every
   `vivado/*.runs/*/runme.log` and fails on any `CRITICAL WARNING` not on a
   short allowlist (the known-benign RUSER/WUSER sideband-width warnings),
   plus a direct sanity check that `coeff_bram_stage_0`'s row shows nonzero
   RAMB36/RAMB18. **Evidence:** this run printed "No unexpected CRITICAL
   WARNINGs in any per-IP runme.log (9 logs checked)" -- a real, working
   gate, not a claim.
5. **(Important) `copy_fsm.v` and `ap_start_seq.v` both ignored `BRESP`** --
   completed on `BVALID` alone, so a DECERR/SLVERR response would still
   report success. **Fix:** both now latch a sticky `err` output on any
   non-OKAY response.
6. **(Important) The clock-rate recommendation in the first version of this
   doc was derived two ways wrong** -- `1/5.933ns` ignored setup/skew/
   uncertainty entirely, and separately ignored that Phase 1 had already
   measured this core's real Fmax. **Fix:** this doc's timing section now
   cites `PHASE1_STATUS.md`'s measured 128.12 MHz and the core's own
   100 MHz HLS compile target directly, with the slack-based figure
   presented as a secondary floor, not the headline number.
7. **(Important) A duplicate `create_clock` in `constraints/genesys2_cv.xdc`
   silently overrode MIG's own generated clock constraint** --
   `CRITICAL WARNING: [Constraints 18-1056] Clock 'sys_clk' completely
   overrides clock 'sys_clk_p'`, flagged by the tool, reported by neither
   version of this doc until now. **Fix:** removed; MIG's own XDC is the
   sole source of truth for this clock. **Evidence:** this build's log has
   no "completely overrides" warning.
8. **(Important) `ui_clk_sync_rst` was never wired into the reset tree** --
   `proc_sys_reset_0` gated only on `mmcm_locked`, which can deassert before
   MIG's UI-side reset sequencing finishes. Harmless today only because
   every master waits on `init_calib_complete`; a latent trap for Phase 3.
   **Fix:** wired into `aux_reset_in` (confirmed active-high by default,
   matching `ui_clk_sync_rst`'s own polarity -- checked, not assumed).
9. **(Important) No sim runner or sim log was ever committed** -- both
   simulations in this phase existed only as commands run by hand.
   **Fix:** `scripts/sim_bram_to_ddr.sh` and `scripts/sim_top.sh` are now
   committed and reproduce both from a clean checkout; this session's own
   `sim_export/xsim/run_all.log` (the run that caught finding 3) is
   force-added alongside `build.log` as evidence.
10. **(Minor, done anyway since it was one line) the reset-button polarity
    assumption** in `constraints/genesys2_cv.xdc`'s comments is not yet
    hardware-verified (Digilent's dedicated memory-controller reset button
    is assumed active-low, matching this design's polarity with no
    inversion) -- noted here as a pre-bring-up check, not just left in the
    XDC comment.

**Deferred as genuinely minor** (recorded, not implemented this pass):
reference-RAM pre-zeroing in `sim/axi_ram.sv` (a skipped write of a
legitimately-zero word would pass undetected); an elaboration-time
`ADDR_W >= $clog2(WORDS)` assertion in `copy_fsm.v`/`coeff_bram_stage.v`; an
inverted explanatory comment in `cnn_subsystem_top.v` about UART timing
margin; a drop-and-retry edge case in the UART status reporter;
`copy_fsm`/`ap_start_seq`'s shared AW/W/B skeleton (two instances is the
right call against premature abstraction; a third would not be);
`copy_fsm`'s one-AXI-transaction-per-word throughput (already documented as
a bring-up simplification, ~0.7-2ms/boot); a sentinel-file suggestion for
detached background builds; splitting `PHASE2_SIM_BYPASS_CAL` into two
independent knobs (calibration bypass vs. word-count reduction) so Task 4
could exercise the full 128-bit-to-256-bit SmartConnect width conversion at
full calibration speed -- correct, but would need another full
simulation re-run to verify, out of proportion for this pass; and exposing
`cnn_engine`'s real `interrupt` port (with GIE/IER enabled) instead of
`ap_start_seq`'s "write acknowledged" proxy for hardware status -- the
current `SIM_HIERARCHICAL_AP_DONE_PROBE` generate-mux pattern was reviewed
and confirmed safe as-is (fail-safe default, simulation-only override), so
this is a clarity improvement, not a safety fix, and is deferred.

## What this means for the next phase

- **BRAM is the real constraint now**, reversing this document's own first
  conclusion. Recovering `coeff_bram_stage_0`'s packing inefficiency
  (~100 RAMB36 available via better width/depth factorization) should be
  the first thing attempted before Phase 3's camera pipeline, not an
  optional optimization.
- **Timing is still not met**, same root cause as before, now on firmer
  ground: decouple `cnn_engine`'s clock from `ui_clk` with a real CDC at
  the AXI boundary, targeting the core's own validated 128.12 MHz Fmax
  (Phase 1) rather than 225 MHz.
- **The `ap_done`/handshake status path has a real, open, unresolved
  finding** (the 374-cycle completion) that should be root-caused before
  Phase 4 needs to trust that signal for anything.

## Working files

    ~/fpga/genesys2-cv-model/bd/create_bd.tcl
    ~/fpga/genesys2-cv-model/rtl/cnn_subsystem_top.v
    ~/fpga/genesys2-cv-model/rtl/{copy_fsm,coeff_bram_stage,ap_start_seq}.v
    ~/fpga/genesys2-cv-model/constraints/genesys2_cv.xdc
    ~/fpga/genesys2-cv-model/scripts/{create_project,build,sim_bram_to_ddr,sim_top}.{tcl,sh}
    ~/fpga/genesys2-cv-model/sim/tb_cnn_subsystem_top.v
    ~/fpga/genesys2-cv-model/sim_export/xsim/run_all.log -- the run that caught finding 3
    ~/fpga/genesys2-cv-model/vivado/utilization.rpt, timing_summary.rpt -- this session's real numbers
    ~/fpga/genesys2-cv-model/build.log
    ~/fpga/genesys2-cv-model/docs/PHASE2_LOG.md -- full per-task engineering log, all rulings and findings
