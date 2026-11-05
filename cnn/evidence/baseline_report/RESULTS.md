# Retained V5 model — complete results snapshot

This report covers the exact V5 epoch-8 checkpoint shown in the 50-photo gallery. It is one trained CNN plus a separate tracking/search pipeline. The main scores below include that pipeline; they are not stand-alone whole-image CNN accuracy.

## Main result

| Measure | Result | Meaning |
|---|---|---|
| Correct-box recall | 79.0% | 6,837 correct boxes / 8,651 labelled drone frames |
| Correct-box precision | 83.0% | 6,837 correct / 8,238 reported outputs, including empty-scene outputs |
| F1 | 81.0% | Combines correct-box precision and recall; not percent accuracy |
| Source-balanced F1 | 81.1% | Gives source/presence groups balanced weight rather than letting long clips dominate |
| True-empty trigger frames | 3 / 328 (0.9%) | Small, correlated author-labelled empty sample; not a universal false-alarm rate |

A correct box requires IoU >=0.5: sufficient overlap with an author-labelled drone. Active outputs with bad boxes count as wrong outputs AND missed correct boxes. There are 1,814 missed correct boxes and 1,401 wrong/empty outputs. Neural confidence is not a measured probability of correctness. The metric threshold0.5 applies to binary tracker-active state, NOT a new neural threshold.

## Model and training

| Item | Value |
|---|---|
| Architecture | Customized narrow YOLOv5 v7-family, ReLU, P2/P3 heads |
| Learned parameters | 331,114 |
| Input | 256 x192 RGB, letterboxed ROI |
| Raw heads | 64 x48 x21 and32 x24 x21; 3 anchors/head;7 fields/anchor |
| Seven fields | x/y/width/height, objectness, drone class, other-flying class |
| Runtime ranking | Raw objectness, with geometry/motion/association gates BEFORE ranking; not strict class rejection |
| Centre | Calculated from the box; no second CNN |
| Training | 8 epochs;6,000 weighted draws/epoch;batch16; warm-started from ROIepoch11 |
| Training learning rate | 0.0001 nominal; body scale0.25; cosine/warmup;AdamW |
| Training selection | Original5Hz native validation/calibration; final10Hz delayed evaluation is separately reported |
| Nominal draws | 48,000 draws WITH replacement, not48,000 unique images |
| Fixed arithmetic | W16 per-layer fraction; activations signed24/F14 in32-bit lanes;48-bit accumulation bound |
| CNN computation | 170,606,592 multiply-accumulates per256x192 call |

Two training classes exist, but the retained runtime ranks flying-object objectness. Other aircraft can therefore trigger. This matches the user’s stated tolerance; it is not a bird/airplane rejection success. ModelEMA weights are retained. Original models and data remain unchanged.

## Training data

32,695 registered TRAIN views, representing 20,918 source/frame keys across six sources. A key is not proof of an independent scene. Several views and neighbouring frames are related. Weighted random draws and crop augmentation mean registered membership does not prove every view was drawn in SGD.

| Source | TRAIN views | Source/frame keys | Groups/recordings |
|---|---|---|---|
| ADE20K | 3,600 | 1,200 | 139 |
| AntiUAV300 | 4,536 | 4,536 | 73 |
| DUT_Anti_UAV | 4,816 | 4,195 | 13 |
| DroneDetectionThesis | 13,593 | 7,195 | 199 |
| SkyDetectionOutdoor | 3,537 | 1,179 | 1179 |
| UAV_CB | 2,613 | 2,613 | 5 |

TRAIN uses original/native pixels where registered and available, crop/scale jitter, colour/flip/blur, and guarded soft background MixUp/contrast. Mendeley is absent from this curated TRAIN manifest; its original validation diagnostic remains preserved with label-quality caveats. Historical hard_negative groups now include explicitly labelled other-flying objects, not necessarily empty pictures. Exact source rows, source paths, boxes, classes and split membership are in raw_evidence/training_manifest.json.gz. No source images were deleted or recopied.

## Evaluation coverage and limitations

All46 original native validation recordings and17,193 frames were replayed. Of these,8,651 contain labelled drones,328 are true-empty frames, and8,214 depict other aircraft without labelled drones. The application metric excludes those8,214 other-aircraft frames by the declared user scope. It retains all drone frames/misses and true-empty frames. Original strict rejection metrics are included below.

| Source | Drone frames | Correct boxes | Recall | Centre inside labelled box |
|---|---|---|---|---|
| DUT_Anti_UAV | 3347 | 2698 | 80.6% | 86.8% |
| DroneDetectionThesis | 5304 | 4139 | 78.0% | 96.4% |

If birds/planes/helicopters MUST all be rejected, strict F1 is 62.9%, precision 52.3%, and negative trigger fraction 56.7%. This model/policy is not suitable for that stricter claim.

Original VAL is repeatedly used for engineering selection, so it is development evidence, not a pristine unseen test. Drone clips include correlated field recordings. Complete OV5640 daylight/panning/hover field acceptance and measured board throughput have NOT been demonstrated. Motion proposal generation, image preprocessing and temporal tracking are still CPU software in these evaluations. A90ms availability delay and10updates/s were assumed; every native frame including startup and misses was scored. Predictions influence future crops only when available. Labels score after decisions and never select runtime crops.

## Every drone video

| Clip | Drone frames | Correct boxes | Recall | Centre inside label |
|---|---|---|---|---|
| video05 | 450 | 424 | 94.2% | 96.7% |
| video10 | 2307 | 1811 | 78.5% | 85.0% |
| video14 | 590 | 463 | 78.5% | 86.3% |
| V_DRONE_002 | 301 | 283 | 94.0% | 97.0% |
| V_DRONE_008 | 302 | 135 | 44.7% | 97.0% |
| V_DRONE_009 | 302 | 229 | 75.8% | 97.0% |
| V_DRONE_031 | 328 | 316 | 96.3% | 97.3% |
| V_DRONE_038 | 304 | 219 | 72.0% | 97.0% |
| V_DRONE_050 | 316 | 289 | 91.5% | 97.2% |
| V_DRONE_052 | 312 | 263 | 84.3% | 97.1% |
| V_DRONE_053 | 300 | 238 | 79.3% | 85.3% |
| V_DRONE_056 | 305 | 148 | 48.5% | 97.0% |
| V_DRONE_067 | 325 | 308 | 94.8% | 97.2% |
| V_DRONE_068 | 311 | 289 | 92.9% | 96.8% |
| V_DRONE_074 | 316 | 148 | 46.8% | 97.2% |
| V_DRONE_079 | 311 | 186 | 59.8% | 97.1% |
| V_DRONE_080 | 300 | 200 | 66.7% | 97.0% |
| V_DRONE_085 | 316 | 296 | 93.7% | 97.2% |
| V_DRONE_093 | 329 | 291 | 88.4% | 97.3% |
| V_DRONE_109 | 326 | 301 | 92.3% | 97.2% |

Complete46-recording results, including other-aircraft recordings, are in native_per_video.csv. All17,193 frame outputs and original truths are in native_all_17193_frames.csv and compressed JSON. Width/height errors remain failures even when the centre is correct.

## Reviewed scene contexts

The same60 timestamps across20 drone clips were chosen before reading predictions. Manual context labels apply ONLY to those exact frames; three timestamps do not classify an entire recording. Small correlated illustrative sample:

| Context | Drone frames | Correct boxes | Recall |
|---|---|---|---|
| building | 2 | 2 | 100.0% |
| sky | 53 | 45 | 84.9% |
| sky_tree_boundary_uncertain | 2 | 1 | 50.0% |
| trees | 3 | 1 | 33.3% |

## Important stand-alone diagnostic

On the original6,319 static validation views at256input, the separately calibrated application diagnostic has 50.0% recall and 62.0% F1. It has no retained-ROI temporal pipeline. It includes original Mendeley label concerns and a different protocol, so it is NOT directly comparable to final79% tracking recall. It does show that the CNN cannot be advertised as universally strong whole-image detection.

| Static source | Correct-box recall |
|---|---|
| ADE20K | n/a |
| AntiUAV300 | 92.5% |
| DUT_Anti_UAV | 28.3% |
| DroneDetectionThesis | 55.4% |
| MendeleyEO | 12.0% |
| SkyDetectionOutdoor | n/a |
| UAV_CB | 4.8% |

## Harder watched videos and external negatives

| Clip | Correct-box recall | Arithmetic/scope |
|---|---|---|
| video13 | 36.2% | Float R3, watched development; NOT newly rerun fixed integer proof |
| video20 | 77.7% | Float R3, watched development; NOT newly rerun fixed integer proof |

External check: 0 triggers / 42 visually reviewed empty frames across six correlated DAVIS scenes, float R3. Intervening native frames maintained state but were unlabelled and NOT scored as confirmed negatives. This is encouraging but a small conditional sample, not a population rate or new integer field test.

## FPGA evidence

| Check | Actual outcome |
|---|---|
| Complete host arithmetic | 241,920 raw values,3 vectors, exact0 difference |
| Actual generated CNN RTL | 80,640 raw values,1 complete real TRAIN vector, exact0 difference;128/256memory-model gates passed |
| Actual core placement/routing | All58,199 routable nets routed;0routing errors;0blackboxes |
| Actual core timing | 100MHz; setup margin+0.309ns;hold+0.056ns;no unconstrained INTERNAL endpoints |
| Actual core resources | 26,828LUT(13.16%);14,037FF(3.44%);266DSP(31.67%);98RAMB36+12RAMB18=208BRAM18 equivalents(23.37%) |
| Decoder host proof | 96queries /768integer fields exact0 difference |
| Decoder actual RTL | 3real-head queries /24integer fields exact0 difference |
| Decoder HLS estimate ONLY | 7,393LUT;6,706FF;34DSP;27BRAM18;not postrouted/combined withCNN |
| External feature buffer | 2.25MiB at declared packed layout;not all FPGA block RAM |
| Exported coefficient file | 665,600bytes (~650KiB);not total system memory |
| Simulated CNN duration | 3,718,308cycles =37.18308ms/call at100MHz, CONDITIONAL memory model |
| Measured board speed | Not measured; do not call37ms actual camera/system throughput |
| Complete system/board | No complete camera/MIG/preprocess/tracker/decoder system fit or physical-board inference claim |

445external input and530external output boundaries were untimed in the out-of-context core check. Internal timing passed; external system constraints still have to be supplied.139DRC warnings were retained; noerrors/criticalwarnings. Core timing is real placement-and-routing evidence, but the design is not a ready-to-program full-board bitstream. The decoder and proposed frontend still need complete integration. You and your teammate are handling the surrounding camera system.

## Numeric variants and newer search trials

| Pipeline | Balanced F1 | Recall | True-empty trigger fraction |
|---|---|---|---|
| Retained R3 float CNN/decoder | 78.7% | 78.2% | 4.6% |
| Retained R3 fixed CNN / float decoder | 80.5% | 78.4% | 1.8% |
| Retained R3 fixed CNN / integer decoder | 81.1% | 79.0% | 0.9% |
| Rejected R4 global256 acquisition | 64.5% | 57.5% | 0.0% |
| Rejected R5 global384 acquisition | 69.0% | 63.9% | 0.0% |
| Rejected R6 sequential slices | 36.1% | 54.7% | 86.6% |

Fixed-point numerical changes can alter later tracking trajectories. Their small gain does NOT prove quantization inherently improves accuracy. R4/R5/R6 search experiments were rejected and have not replaced retained R3. R6 had54.7% recall and284/328true-empty trigger frames; it is clearly worse and was NOT adopted. R6 is included only if its full report existed when this snapshot was created; otherwise it is still a separate live experiment. No new training happened during these frontend trials.

## Files to open

- charts/all_drone_videos.png — all20 drone recordings, including weaker ones.
- charts/training_history.png and training_epochs.csv — every epoch, with its original protocol.
- native_per_video.csv / native_per_source.csv — complete breakdowns.
- native_all_17193_frames.csv — frame-by-frame predictions, truth boxes, overlaps, activity and neural scores.
- completed_pipeline_comparisons.csv — matched arithmetic variants and completed search trials.
- dataset_counts.csv / compressed training manifest — exact registered data membership and paths.
- raw_evidence/ — original saved reports plus compressed native labels/predictions.
- model/epoch_08.pt — exact retained checkpoint (includes training/recovery state, not just deployment weights).
- model/quantized_fx.pt and coefficients.bin — matching fixed-point reference and hardware coefficients.
- video_locations.csv — annotated video paths.
- ../model_photo_examples_50/index.html —50 selected explanatory photos.

## Reading the numbers

Recall: how many actual drone frames got a correct box. Precision: how many outputs were correct. F1: a balance of those two, not a generic accuracy percentage. IoU: overlap between predicted and labelled boxes;0means no overlap,1means exact overlap. Centre-inside-label is an extra location diagnostic, not a substitute for correct-box IoU. A pretty selected photo or good video does not establish overall performance.

Evidence hashes and checkpoint identity are in SNAPSHOT.json. This folder is a snapshot; original evidence files remain preserved.
