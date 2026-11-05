# Genesys 2 Drone-Detection CNN — Handoff

**Date of this package:** 2026-10-29
**Board:** Digilent Genesys 2 (Xilinx Kintex-7 XC7K325T), free Vivado 2023.2 on Linux
**Repo:** `~/fpga/genesys2-cv-model` (this zip is a snapshot of the working tree, not a git clone — see "Git state" below)

## 1. What this is

A standalone (no camera yet) FPGA pipeline that takes a 256x192 image loaded
over JTAG, runs it through a 331K-parameter YOLOv5-style CNN (`cnn_engine`,
HLS-generated, frozen/validated in an earlier phase), decodes the raw output
into a bounding box + confidence (`decode_work_heads`, also pre-synthesized
HLS from the same handoff), and transmits the result over UART. All driven
by a hardware auto-sequencer (`pipeline_seq.v`) — no PC/JTAG intervention
needed once triggered.

**This is real, hardware-validated work** — every number in this document
came from an actual Genesys 2 over JTAG, not simulation or estimation,
unless explicitly marked otherwise.

## 2. Current status: working, flashed, benchmarked

- Full pipeline (CNN → decoder → register capture) runs automatically on
  real hardware, triggered once per boot/reset.
- Output cross-checked bit-for-bit against an independent Python reference
  implementation (`scripts/decode_heads.py`, a faithful port of the
  reference decoder algorithm) — exact match.
- Timing closed on the current build: **WNS = +0.040ns, MET** (see §4 for
  what that number actually means — it's not where you'd guess).
- Flashed bitstream included in this package: `bitstream/cnn_subsystem_top.bit`.
- **100 real labeled samples benchmarked twice** (100MHz and 140MHz
  clock configs) against real field-footage drone video — see §5.

## 3. Architecture (as of this snapshot)

```
MIG (DDR3) ─┬─ cnn_engine_0 ────────────── clk_out1 (140MHz, build-time CNN_CLK_MHZ)
            ├─ decode_work_heads_0 ──────── clk_out2 (100MHz, fixed)
            ├─ coeff_bram_stage_0 / copy_fsm_0  (loads 41,600-word coefficient set)
            ├─ jtag_axi_0           (JTAG debug-bridge, for manual test/load)
            └─ pipeline_seq_0       (hardware auto-sequencer, AXI-Lite master,
                                      read+write capable)
pipeline_seq_0 → uart_tx → uart_tx_pin (board UART)
```

- `cnn_engine` and `decode_work_heads` run on **independently clocked**
  domains (added 2026-10-29) sharing one `clk_wiz` MMCM, connected across
  `axi_clock_converter` CDC bridges. This was a deliberate decoupling:
  every earlier timing experiment found the decoder's own arithmetic
  (`transformed()` / `width_q()` multipliers) was the thing that got tight
  at higher shared clocks — `cnn_engine` itself was never the limiter. By
  giving the decoder its own fixed, already-proven-safe clock, `cnn_engine`
  can be pushed faster independently.
- `pipeline_seq.v` is a micro-programmed FSM (`k_kind[]/k_addr[]/k_data[]`
  arrays) that: writes `cnn_engine`'s pointers + `ap_start` → polls its
  `ap_done` → writes `decode_work_heads`'s pointers + 14 config registers
  (identity/no-motion case) + `ap_start` → polls its `ap_done` → captures 7
  `BEST_O` registers → transmits sync byte `0xAA` + 28 bytes over UART.
- No camera RTL anywhere in this hierarchy — deliberate, see §7.

## 4. Timing — read this carefully, it's subtle

`scripts/build.tcl` prints a single global WNS number
(`get_timing_paths -delay_type max`, worst path in the *entire* design).
That number has meant **different things at different points this session**
and conflating them is a real trap:

- At 125MHz (shared clock, before decoupling): the global worst path
  *was* `decode_work_heads_0`'s own arithmetic. WNS=+0.040ns meant "the
  decoder is barely closing timing."
- At 140MHz (current, decoupled): WNS is *also* +0.040ns, but checking the
  **per-clock breakdown** in `vivado/timing_summary.rpt` shows this is a
  coincidence — the global-worst path is now inside the **MIG DDR3 PHY's
  own internal `mem_refclk` domain**, completely unrelated to `cnn_engine`
  or the decoder. `cnn_engine`'s own domain actually has **+0.195ns**
  margin at 140MHz, and the decoder's own domain has **+1.051ns** margin
  (comfortable, now that it's back down to its originally-proven-safe
  100MHz). Don't trust the single headline number without checking which
  clock domain it's actually in — `grep -n "Intra Clock Table" -A N
  vivado/timing_summary.rpt` is how this was found.

Full timing-closure history (200MHz → 150MHz → 135MHz → 125MHz → 140MHz
decoupled), with real WNS and critical-path detail for each, is in
`docs/PHASE2_LOG.md`.

## 5. Real data gathered (all included in this package under `docs/`)

| Dataset | n | Domain | Mean confidence | Location accuracy |
|---|---|---|---|---|
| `batch_eval_100samples/` | 100 (50 unique, x2) | Documentation/gallery composite photos | drone 37.5%, bg 6.2%, bird 6.8%, airplane 32.2% | median 1.4px, mean 23.8px, 77% within 30px |
| `batch_eval_drone_dataset_100samples/` | 100 (10 videos x10 frames) | Real field/sky footage (DroneDetectionThesis dataset), **100MHz** | 64.7% mean | mean 12.83px, median 9.10px, 96/100 within 32px (10% of diagonal) |
| `batch_eval_drone_dataset_100samples_140mhz/` | same 100 frames | Same, **140MHz decoupled** | 64.70% (bit-exact match) | identical — confirms clock change is purely a timing win |

**Why two domains matter**: the gallery-photo set is documentation
composites, not realistic deployment imagery. The real-video set matches
the user's actual deployment condition ("a field on clear or overcast
skies") and is the more trustworthy number for judging real-world
performance — confidence jumps from 37.5% to 64.7% just from domain match,
nothing about the hardware or model changed.

**Known weak case**: `V_DRONE_078` (treeline/clutter background) is the
one video with real outliers (4 of the 4 total outliers across both
drone-video runs, up to 126px off) and the lowest per-video confidence
(37.6%). Not investigated further — worth a closer look if this dataset
becomes a recurring benchmark.

**Timing, measured not estimated** (100MHz → 140MHz, same 100 real frames):

| | 100MHz | 140MHz decoupled | change |
|---|---|---|---|
| mean CNN time (JTAG-measured) | 63.08ms | 51.81ms | −17.9% |
| mean decoder time | 10.71ms | 10.74ms | ~0 (unchanged clock) |
| mean total (JTAG-inflated) | 73.79ms | 62.55ms | −15.2% |

`cnn_engine` is cycle-count deterministic (3,774,628 cycles, fixed —
confirmed by tight clustering of measured times across different images
despite poll-count variance). Cycle-exact (JTAG overhead removed):
~37.75ms @100MHz, ~30.2ms @125MHz, ~27.0ms @140MHz.

**JTAG overhead, isolated and measured directly**: ~3-4ms per JTAG
transaction; ~25-26ms total overhead on a typical CNN trigger-to-done
poll loop at 100MHz. Real end-to-end estimate with JTAG removed (100MHz
build): **~43-47ms** (37.75ms CNN + ~5-9ms decoder, less tightly bounded
since decoder compute is comparable to JTAG poll granularity).

## 6. Known gaps / not yet verified

- **UART bytes on the physical pin were never observed.** The RTL is real,
  flashed, and exercised (the decoder's register capture completing proves
  `pipeline_seq_0` reached its UART-transmit states), but this environment's
  Genesys 2 UART channel isn't bound to a driver here — nobody has actually
  watched real bytes come out the pin. Verify with a USB-UART adapter +
  terminal before trusting this path end-to-end.
- **One unexplained register-read oddity**: `cnn_engine`'s `AP_CTRL` was
  once observed as `0x00000001` (ap_start still set, ap_idle not set) right
  after a completed auto-triggered run, instead of a clean idle state.
  Possibly just a read-timing artifact; not root-caused. Flagged in
  `docs/PHASE2_LOG.md`'s pipeline_seq section — worth revisiting for any
  continuous/real-time retrigger design.
- **30Hz is not achievable as currently built.** `cnn_engine`'s own cycle
  count (~3.77M cycles) is roughly fixed regardless of clock (55 ops reuse
  shared compute hardware sequentially) — even an optimistic ~140MHz gives
  ~27ms for the CNN alone, and that's before camera/decode/transmit
  overhead. A user-requested 15-20ms frame-to-bbox latency target is **not
  reachable via clock tuning** — it needs either accepting a larger number
  (realistically ~27-30ms+ range) or a real HLS re-architecture for more
  parallelism, which needs Vitis HLS (not installed/available on this
  machine) and was explicitly scoped as separate future work this session.
- **Two real hardware/tooling bugs found and fixed this session** (details
  in `docs/PHASE2_LOG.md`), worth knowing about if you touch these areas
  again:
  1. `pipeline_seq.v`'s FSM state register was 1 bit too narrow (3 bits for
     9 states), causing a silent encoding collision and an infinite
     auto-retrigger loop. Fixed (now 4 bits). If you add more FSM states,
     double check the width against `2^N >= state_count`, don't assume.
  2. **Multi-beat AXI burst reads *and* writes land in reverse order**
     relative to ascending address, when driven through this project's
     `jtag_axi`/`hw_axi` Tcl helper pattern. Both sides are fixed in the
     batch scripts' `axi_read_burst`/`axi_write_burst` helpers — but this is
     a Tcl/`hw_axi`-specific quirk, not an AXI protocol fact, so if you
     write new Tcl tooling against `jtag_axi`, re-verify this, don't assume
     ascending order.

## 7. Explicitly out of scope this phase

- **No camera RTL.** JTAG-loaded photos stand in for a live camera feed.
  A separate, *simulated-only* OV5640→HDMI pipeline exists at
  `~/fpga/genesys2-ov5640-hdmi` (YUV422→RGB888→TMDS from fabric) but is
  **unbuildable on the free Vivado tier on Linux** (XC7K325T licensing) —
  not integrated here, not attempted this session.
- **Multi-frame tracking.** The CNN here is single-frame; a separate
  tracker (mentioned as running on a different board, the Basys 3, in an
  unrelated project) is a distinct pipeline, not part of this one.
- **HLS re-architecture for real parallelism** (the only real path to the
  15-20ms latency target) — needs Vitis HLS, not available on this
  machine.

## 8. Git state — read before committing anything

This repo **does** have a git history (6 commits through "Phase 2
post-review fix pass"), but **almost everything described in this
document is currently uncommitted** in the working tree — that was a
deliberate choice this session (standing instruction: no commits unless
explicitly asked). Before doing anything destructive, run `git status`
in the live repo and decide what to commit — don't assume the zip
contents are already safely in git history anywhere.

## 9. How to rebuild / reflash from scratch

```bash
source /tools/Xilinx/Vivado/2023.2/settings64.sh   # bash, not fish
cd ~/fpga/genesys2-cv-model
vivado -mode batch -source scripts/create_project.tcl
CNN_CLK_MHZ=140 vivado -mode batch -source bd/create_bd.tcl   # sets clk_out1
vivado -mode batch -source scripts/build.tcl 2>&1 | tee build.log
vivado -mode batch -source scripts/program.tcl                 # flash, volatile
```

Or just flash `bitstream/cnn_subsystem_top.bit` directly (included in this
package) via `scripts/program.tcl` / Vivado Hardware Manager — no rebuild
needed to reproduce this snapshot's exact behavior.

To re-run a real-hardware batch test: see `docs/batch_eval_drone_dataset_100samples_140mhz/batch_run_video.tcl`
and its `analyze.py` for the reproducible pattern (manifest-driven JTAG
burst write/trigger/poll/read, decode + ground-truth scoring).

## 10. Package contents

```
HANDOFF.md                  this file
PHASE1_STATUS.md            Phase 1 (CNN core regeneration) status
PHASE2_STATUS.md            Phase 2 status (header updated to point at real-hardware state)
docs/PHASE2_LOG.md          the full engineering log — every experiment, bug, and fix, in order
docs/batch_eval_100samples/              gallery-photo batch (documentation composites)
docs/batch_eval_drone_dataset_100samples/      real video batch, 100MHz baseline
docs/batch_eval_drone_dataset_100samples_140mhz/  real video batch, 140MHz decoupled (current)
rtl/                         all Verilog source (cnn_core/, decoder_core/, pipeline_seq.v, etc.)
bd/create_bd.tcl             block design script (source of truth, regenerates vivado/)
scripts/                     create_project/build/program.tcl, JTAG test scripts, Python packers
sim/                         testbenches
constraints/                 XDC
bitstream/cnn_subsystem_top.bit   flashable bitstream matching this snapshot's exact RTL
vivado/timing_summary.rpt, vivado/utilization.rpt   real post-route reports for this build
```

`vivado/` (the generated project itself, ~830MB) and HLS/sim scratch
directories (`cnn_hls_work/`, `cnn_rtl_sim_work/`) are intentionally
**not** included — regenerate via the scripts above, or ask whoever ran
this session for them directly if you need the HLS intermediate files.
