# Retained CV model â€” V5 epoch 8 + R9

This is the model Ethan preferred in the later video demonstrations. It is NOT the old 521,757-parameter compact detector or the untrained 64,853-parameter proposal. The exact retained weights are preserved; no training was started during packaging.

## Contents

- weights/epoch_08.pt: trained floating-point checkpoint including EMA weights.
- weights/quantized_fx.pt: frozen fixed-point reference used with the routed CNN core.
- software/: portable CPU video runner, original architecture, decoder and tracker, vendored YOLOv5 source/license. Read software/README.md.
- config/: preferred R9 settings, decoder anchors and memory-offset metadata.
- fpga/: complete CNN HLS source/coefficients/test vectors; generated CNN RTL, ROM files, routed checkpoint/reports; integer decoder HLS/RTL and tests. Read fpga/README.md.
- evidence/preferred_r9/: current preferred policy's saved results. config/PREFERRED_INFERENCE_R9.json is the concise summary.
- evidence/baseline_report/: earlier same-model baseline report, with different acquisition settings. Its numbers and local links are historical. Do not mix those settings/results with R9.
- examples/photo_examples_50/: 20 training examples, 15 successes and 15 misses/wrong boxes, with provenance. Examples illustrate conditions; they are not an unbiased accuracy estimate. Retain source credits and dataset usage conditions.
- reference_source/campaign/: original training/evaluation scripts and their local dependency closure. These retain historical dataset paths and are for adaptation, not a portable one-command training environment.

## Model and pipeline

331,114 learned parameters. Input is a **256 x 192 RGB crop**, not necessarily the camera's whole image. Adapted YOLOv5 v7.0 narrow backbone, C3 blocks and ReLU; two detection heads: P2 stride 4 (64 x 48 x 21) and P3 stride 8 (32 x 24 x 21). Three anchors per head, seven values per anchor: four box coordinates, objectness, two class scores. Classes are drone and other_flying. The centre comes from decoded box coordinates, not a second CNN.

Software motion detection proposes regions and compensates for approximate camera translation. A single-target tracker also proposes a search region using previous detections. Crops are resized/letterboxed to RGB input. The integer decoder selects candidates, then R9 maintains one track. At most two crops per scheduled update. Small or stationary drones, clutter, camera movement and loss of acquisition remain limitations. Do not resize the whole video straight to 256 x 192 and assume the published pipeline results still apply.

R9: acquire 0.15, maintain 0.06, two hits to acquire, one missed update allowed. The replay schedules up to 10 updates/second with 90 ms **assumed** result availability. These are software simulation settings; neither is a measured complete-system FPGA speed.

## Saved results and their limits

On the saved native-frame application validation: correct-box recall 79.96% (6917/8651 drone frames), precision 82.83%, F1 81.37%; outputs on true empty frames 3/328. Correct boxes require IoU >= 0.5. The complete replay has 17,193 frames from 46 recordings; the application metric excludes 8,214 other-aircraft frames. Related video frames are correlated, and watched development footage is not a new independent field test. Difficult building-background scenes remain weak. Do not present these numbers as performance on every environment.

The same trained CNN core passed out-of-context placement/routing at 100 MHz: 26,828 LUTs (13.16%), 14,037 FFs (3.44%), 266 DSPs (31.67%), 98 RAMB36 + 12 RAMB18 (23.37% BRAM). Internal setup slack 0.309 ns and hold slack 0.056 ns. Full camera, DDR/MIG, preprocessing, tracking, decoder integration and physical board inference are NOT demonstrated. External core interfaces still need real timing/system constraints. This is not a ready-to-program full-detector bitstream.

## Training/retraining

The retained checkpoint completed eight additional epochs from an earlier checkpoint. Its internal epoch field is 9 because the trainer saves the next epoch to resume; the file is the completed epoch-8 checkpoint. Training selection: 32,695 views, 20,918 source keys; replacement sampling was used. Source/validation manifests and config/history are in evidence/baseline_report/raw_evidence/ (some gzip-compressed). Original absolute paths must be remapped without changing split membership. Bulk datasets and earlier initialization checkpoints are deliberately not bundled. Inference needs neither. Reproducing training from its original initialization requires those original data assets/checkpoints, dataset permissions and adaptation of the reference training scripts. Verify DirectML gradient behaviour or use a supported CPU/CUDA loss path before retraining. Do not silently mix test/video demonstration frames into TRAIN.

## Provenance and research

- Ultralytics YOLOv5 v7.0, commit 915bbf294bb74c859f0b41f1c23bc395014ea679: https://github.com/ultralytics/yolov5/tree/v7.0 . Vendored GPL-3.0 license retained. This is a custom adaptation, not stock YOLOv5 accuracy or a published drone model reproduced unchanged.
- Hobden, Srivastava, Nurellari, FPGA-Based CNN for Real-Time UAV Tracking and Detection (2022): https://doi.org/10.3389/frspt.2022.878010 . Inspired motion proposals plus CNN; this implementation is not their architecture reproduced exactly.
- ByteTrack: https://arxiv.org/abs/2110.06864 . Inspired matching lower-confidence observations; the included controller is simplified single-target logic, not full ByteTrack.
- Computation reuse/memory-bandwidth background: https://doi.org/10.1145/2684746.2689060 . The included shared engine is project-specific.
- Genesys 2 documentation: https://digilent.com/reference/programmable-logic/genesys-2/start . Use actual part/resource limits and board constraints.

No bulk pretrained download or dependency installer runs automatically. Historical results contain Ethan's local paths for traceability; these need not exist to run software/run_video.py. Verify hashes in SHA256SUMS.json. No board programming, Windows changes or background schedule is bundled.
