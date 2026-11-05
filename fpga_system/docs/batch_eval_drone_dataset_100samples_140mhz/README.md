# 140MHz decoupled-clock batch eval (10x10 real drone videos)

Same 100 real frames (10 videos x 10 frames, DroneDetectionThesis dataset) as
`../batch_eval_drone_dataset_100samples/`, re-run against the live repo's
140MHz decoupled-clock bitstream (cnn_engine on clk_out1=140MHz, decoder on
clk_out2=100MHz via independent clk_wiz_0 outputs + CDC converters).

## Functional correctness
Raw decode outputs (x, y, w, h, confidence, raw_objectness) are **bit-exact
identical** to the original 100MHz baseline on all 100 frames (only
cnn_polls/dec_polls differ, as expected from JTAG poll-timing jitter). This
is the expected result for a clock-only change to a fixed-point deterministic
pipeline, and confirms zero functional regression at batch scale, not just
on the single known-good test image used for the earlier bit-exact check.

## Accuracy vs. ground truth (identical to 100MHz baseline, as expected)
| metric | 100MHz baseline | 140MHz decoupled |
|---|---|---|
| mean distance (px) | 12.83 | 12.83 |
| median distance (px) | 9.10 | 9.10 |
| mean confidence | 64.7% | 64.70% |
| within 10% of diagonal (32px) | 96/100 | 96/100 |

Identical because the geometry/confidence outputs are bit-exact per-frame;
accuracy against ground truth is a function of those values, not of clock
frequency. V_DRONE_078 remains the one problem video (treeline camouflage),
same as the 100MHz run.

## Timing (JTAG-poll-inflated, but same methodology both sides -> comparable)
| metric | 100MHz baseline | 140MHz decoupled | delta |
|---|---|---|---|
| mean cnn_ms | 63.08 | 51.81 | -17.9% |
| mean dec_ms | 10.71 | 10.74 | ~flat (decoder still at 100MHz) |
