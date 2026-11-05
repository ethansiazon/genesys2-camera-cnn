# Phase 1: CNN core regeneration — COMPLETE

Regenerated the CNN engine HLS core from source (cnn_hls/cnn_engine.cpp) under
Vivado/Vitis HLS 2023.2, targeting xc7k325tffg900-2, matching this machine's
toolchain instead of the original 2026.1 build.

## Result: byte-identical functional match

Substituted our freshly-synthesized RTL into Ethan's existing RTL simulation
harness (cnn_rtl_simulation/, same tb.sv/axi_ram.sv, same trained coefficients
and real training-frame test input) and ran the full simulation.

`cmp` against the original's saved actual_rtl_results.bin: EXIT 0, byte-identical,
all 368,640 bytes. Full real computation: 3,774,628 cycles, 575,438 feature
reads, 331,008 feature writes, 42,842 coefficient reads, completed via ap_done
interrupt.

## What this means

- The 2026.1 -> 2023.2 tool version gap is NOT a blocker. Internal resource
  scheduling differs (different generated submodule names/count -- 80 files
  vs their 98, zero SHA256 matches on individual files), but the top-level
  AXI interface and the actual numerical output are identical.
- Safe to build the rest of the system (Phase 2+) against this regenerated
  core rather than fighting the version-locked original .dcp/.v files.
- Fmax estimate from our synthesis: 128.12 MHz (comfortably above their
  100MHz target clock).

## One wrinkle for next time

The HLS output's ROM .v wrapper files need their accompanying .dat files
copied alongside them for simulation -- missing on the first attempt, which
silently produced a false-positive "pass" (225 cycles, zero memory accesses,
core effectively did nothing because a missing ROM value zeroed a loop bound).
Always check cycle count and read/write-beat counts look like REAL work, not
just that the run completed without error.

## Working files

~/fpga/genesys2-cv-model/cnn_hls_work/     -- HLS project, regenerated RTL
~/fpga/genesys2-cv-model/cnn_rtl_sim_work/ -- simulation harness + our RTL,
                                               reference_actual_rtl_results.bin
                                               preserved for future comparison
