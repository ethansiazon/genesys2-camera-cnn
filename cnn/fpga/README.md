# FPGA handoff: core exists, system integration remains

Original tool release: Vivado/Vitis HLS 2026.1, xc7k325tffg900-2. A different release may need regenerating from source; a DCP is version-sensitive. No CNN system .bit is supplied because there is no complete board implementation yet.

## Inspect without rebuilding

Open cnn_routed_core/routed.dcp in Vivado with Open Checkpoint. This is the actual complete 55-operation trained CNN core routed out of context, with its saved utilization/timing/route reports. Do not try Program Device with a DCP. For editing, cnn_routed_core/rtl/ has all generated Verilog and ROM .dat files. cnn_hls/ has the editable C++ engine, generated program, packed weights and vectors. Preserve the .dat files and coefficient binary; RTL alone does not supply the trained weights to external memory.

## Reproduce the core build

Copy cnn_hls to a short writable working folder, change into that folder, then run:
```
vitis_hls -f synth.tcl
```
This script resets its generated HLS project in the working folder. It synthesizes the complete core and does not program hardware. The included test_engine.cpp, three input binaries, expected.npy and HOST_NUMERICAL_CHECK.json preserve the original numerical tests. The synthesized core has 256-bit feature-memory AXI and 128-bit coefficient-memory AXI interfaces with AXI-Lite control. It is not a pixel-stream module.

To repeat the saved RTL route, copy cnn_routed_core to a NEW short working directory, change into it and run:
```
vivado -mode batch -source route.tcl
```
The legacy script writes checkpoints/reports in its current directory. Preserve the saved evidence by using a copy. Inspect timing_values.json, timing.rpt, drc.rpt and route_status.rpt; successful process exit alone does not prove timing closure. The original script does not guard free RAM. Do one compiler at a time, keep at least 1.5 GiB free, and use the camera package's guarded-build pattern or an equivalent owned-process guard before long runs on a small laptop.

Decoder: copy decoder_hls/ to a working folder, run vitis_hls -f decoder_synth.tcl; decoder_cosim.tcl supplies the corresponding RTL test. Read both before invoking because they reset/open the generated decoder project. Saved HOST_CHECK.json and evidence/hardware/ report the previous tests. decoder_rtl/ contains the generated implementation.

## Memory / quantization contract

cnn_engine(features, coefficients) reuses shared compute hardware across 55 operations. program.h is authoritative for allocation and head offsets. Feature allocation is 73,728 256-bit words (2,359,296 bytes); coefficients are 41,600 128-bit words (665,600 bytes). Input allocation is 49,152 256-bit words. These external-memory allocations are NOT included as on-chip BRAM in the core fit percentages. Read/write packing is demonstrated in test_engine.cpp; engine.cpp and program.json define layout, channel padding, operation ordering and offsets. Do not assume a tightly packed RGB byte array can be sent directly to this port.

Weights use 16-bit per-layer fixed-point scales; internal activations/biases use 24-bit values with 14 fractional bits and defined rounding/saturation; accumulation is wider. Output storage in this revision uses 32-bit lanes to preserve raw Q14 heads for the integer decoder. Exact per-layer scales and rounding bounds are in QUANTIZED_MODEL_METADATA.json and code. This is not a generic INT8 export.

Decoder metadata is in config/DECODER_PREPARED.json and decoder_hls/PREPARED.json. It converts raw logits/anchors to candidate box/centre and confidence with integer arithmetic and ROI mapping. Preserve head order, strides [4,8], trained anchors and map back from crop to full-frame coordinates. Seven values per anchor include both class scores. Do not drop a class or head without retraining/exporting and validating the change.

## Next integration work

1. Establish correct camera colour, pixel ordering, frame timing and complete frames with the camera-only project.
2. Implement the camera-to-memory path and DDR/MIG/interconnect/control for the CNN engine, including trained coefficient loading. Budget actual buffer storage and bandwidth.
3. Implement matching motion/crop/resize/RGB normalization and exact feature packing. If these remain on a CPU, document that system partition explicitly.
4. Connect decoder and tracking/controller, cross clock domains correctly and compare fixed test vectors and recorded scenes against the supplied software.
5. Constrain all external interfaces, place/route the complete system and measure real latency, throughput and total resources on the board.

No physical-board inference, complete-system fit, camera-integrated FPS or field-accuracy claim is established by the core reports. Keep the camera build independent until a combined design passes its own checks. No actuator interfaces are included.


## Actual RTL simulation harness included

cnn_rtl_simulation/ contains the complete generated core plus AXI RAM model, tb.sv, hexadecimal input/coefficients, rtl.prj and run.tcl used by the saved numerical RTL check. These are simulation memory models, not a real DDR controller. Preserve their provenance and compare new output against the saved actual_rtl_results.bin; do not assume any simulation pass from process exit alone. With Vivado tools on PATH, work in a copy, inspect tb.sv and use xvlog -prj rtl.prj, xelab tb -s cnn_test, and xsim cnn_test -tclbatch run.tcl. This may be a long simulation; it was NOT rerun during handoff.

reference_source/campaign/shared_engine/ includes original export/generation history. Some exporters expect earlier trial checkpoints/builds not bundled here. For the current model use the already-generated program/coefficients and matching RTL. Adapting an exporter to a changed model requires reviewing those dependencies, scales, vectors and resource/timing evidence again.
