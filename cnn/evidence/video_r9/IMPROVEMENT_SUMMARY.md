# V5 improvement check — 18 October 2026

**Use the same trained V5 model, with the newly checked R9 confidence setting.** The original model, original settings and original videos are preserved. No retraining was needed for this small improvement.

The model sometimes produced a useful but weak response. We tested lowering the high-confidence requirement from 0.25 to 0.15. It still requires two matching observations before starting a track. This setting also refreshes the track's high-confidence timer; the lower maintenance requirement stays 0.06.

| Check | Previous | R9 |
|---|---:|---:|
| Correct boxes across original validation drone frames | 6,837 / 8,651 (79.03%) | 6,917 / 8,651 (79.96%) |
| Precision of outputs in the application scope | 82.99% | 82.83% |
| F1 | 80.96% | 81.37% |
| Author-labelled empty frames with an output | 3 / 328 | 3 / 328 |
| Video 20 correct boxes | 1,271 / 1,635 (77.74%) | unchanged |
| Video 13 correct boxes | 660 / 1,914 (34.48%) | 737 / 1,914 (38.51%) |
| Video 13 centre inside labelled drone | 40.44% | 45.09% |
| Reviewed external background frames with an output | 0 / 42 | 0 / 42 |

The full original 46-recording, 17,193-frame replay completed first. The configuration passed the predeclared validation gate before the watched videos and matched external backgrounds were evaluated. None of the 20 original validation drone clips lost correct-box recall. There were 80 extra correct boxes and 33 extra false/poor boxes, so precision decreased slightly. There were no activation overflows. Video and CSV frame counts, saved model identities, unchanged labels, scores and start/middle/end video decodes were checked independently. Both preview sheets were visually reviewed.

**This is a modest improvement, not a solved building-scene problem.** Video 13 still misses many drones. These are reused development recordings, not unseen field accuracy. The small external sample does not establish a population false-alarm rate. Other aircraft are excluded from the application score as agreed; strict results remain in the raw report.

## Files to open

- [Video 20](video20_v5_fixed_detected.mp4)
- [Video 13](video13_v5_fixed_detected.mp4)
- [Comparison](COMPARE.json)
- [Verification](VERIFIED.json)
- [Chosen configuration](../../../genesys2_feasibility_campaign/PREFERRED_INFERENCE_R9.json)

Green box/cross = labelled drone and centre. Magenta = model prediction and centre. A correct box has at least 0.5 intersection-over-union with a drone label; a close centre with a poor-sized box is not counted as a correct box.

## FPGA status and next useful work

The unchanged 331,114-parameter CNN core already passed actual RTL numerical checks and a complete core place-and-route fit at 100 MHz. This does not establish a complete camera/DDR/frontend/tracker/decoder system or actual board operation. The replay still uses CPU motion proposals, crop/resize and tracking, with 90 ms assumed output availability and a 10 Hz update target. Playback 30 fps is not inference speed.

Keep this architecture. The next training experiment should target actual TRAIN-only weak-drone crops and confusing buildings/trees while retaining the majority of original examples, rather than training random extra epochs or replacing the architecture again. No new training was started in this step. Real OV5640 daylight footage is the relevant future field check.
